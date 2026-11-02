"""Organisation and search: ratings, tags, albums, filters, exclusions (EPIC 4/6, LIB-003)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fotomind.modules.storage.paths import is_excluded, normalise_exclude_patterns
from tests.unit.test_library_api import _ingest, _register, _report

SHAS = [f"{i:x}" * 64 for i in range(1, 7)]


def _seed(client: TestClient) -> dict[str, str]:
    """Four assets with different cameras, dates and paths. Returns name -> asset id."""
    root = _register(client)
    files = [
        _report(
            "2023/Rome/colosseum.jpg",
            SHAS[0],
            captured="2023-04-10T09:00:00+00:00",
            camera_model="EOS R6",
            lens_model="RF 24-105",
        ),
        _report(
            "2023/Rome/forum.jpg",
            SHAS[1],
            captured="2023-04-11T09:00:00+00:00",
            camera_model="EOS R6",
        ),
        _report(
            "2024/beach_day.jpg",
            SHAS[2],
            captured="2024-08-01T12:00:00+00:00",
            camera_model="iPhone 15",
        ),
        _report(
            "2024/clip.mp4",
            SHAS[3],
            captured="2024-08-02T12:00:00+00:00",
            asset_type="video",
            mime_type="video/mp4",
        ),
    ]
    result = _ingest(client, root["id"], files=files)
    return {f["relative_path"].rsplit("/", 1)[-1]: f["asset_id"] for f in result["files"]}


def _names(client: TestClient, **params) -> list[str]:
    resp = client.get("/api/v1/assets", params=params)
    assert resp.status_code == 200, resp.text
    return [a["display_name"] for a in resp.json()["items"]]


def test_search_matches_name_path_camera_and_tags(db_client: TestClient) -> None:
    ids = _seed(db_client)
    assert _names(db_client, q="rome") == ["forum.jpg", "colosseum.jpg"]  # folder name
    assert _names(db_client, q="iphone") == ["beach_day.jpg"]
    assert _names(db_client, q="rome colos") == ["colosseum.jpg"]  # terms are ANDed
    assert _names(db_client, q="24-105") == ["colosseum.jpg"]  # lens
    assert _names(db_client, q="_") == ["beach_day.jpg"]  # LIKE wildcards are literal
    assert _names(db_client, q="100%") == []

    db_client.patch(f"/api/v1/assets/{ids['clip.mp4']}", json={"tags": ["Holiday"]})
    assert _names(db_client, q="holi") == ["clip.mp4"]


def test_filters_and_sort(db_client: TestClient) -> None:
    ids = _seed(db_client)
    assert _names(db_client, camera="EOS R6") == ["forum.jpg", "colosseum.jpg"]
    assert _names(db_client, date_from="2024-01-01", date_to="2024-08-01") == ["beach_day.jpg"]
    assert _names(db_client, asset_type="video") == ["clip.mp4"]
    assert _names(db_client, sort="oldest", limit=2) == ["colosseum.jpg", "forum.jpg"]

    page = db_client.get("/api/v1/assets", params={"sort": "oldest", "limit": 2}).json()
    rest = db_client.get(
        "/api/v1/assets", params={"sort": "oldest", "limit": 2, "cursor": page["next_cursor"]}
    ).json()
    assert [a["display_name"] for a in rest["items"]] == ["beach_day.jpg", "clip.mp4"]

    db_client.patch(f"/api/v1/assets/{ids['forum.jpg']}", json={"rating": 4})
    db_client.patch(f"/api/v1/assets/{ids['beach_day.jpg']}", json={"rating": 2})
    assert _names(db_client, min_rating=3) == ["forum.jpg"]
    assert db_client.get("/api/v1/assets", params={"min_rating": 6}).status_code == 422


def test_rating_and_tags_on_one_asset(db_client: TestClient) -> None:
    ids = _seed(db_client)
    url = f"/api/v1/assets/{ids['forum.jpg']}"
    detail = db_client.patch(url, json={"rating": 5, "tags": [" Rome  2023 ", "family", "FAMILY"]})
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["rating"] == 5
    assert body["tags"] == ["Rome 2023", "family"]

    # Tag names are case-insensitive; the first spelling is kept.
    db_client.patch(f"/api/v1/assets/{ids['colosseum.jpg']}", json={"tags": ["Family"]})
    assert _names(db_client, tag="FAMILY") == ["forum.jpg", "colosseum.jpg"]
    assert _names(db_client, tag=["family", "rome 2023"]) == ["forum.jpg"]

    # Replacing tags drops unused ones from the vocabulary.
    db_client.patch(url, json={"tags": []})
    facets = db_client.get("/api/v1/library/facets").json()
    assert facets["tags"] == [{"value": "family", "count": 1}]
    assert db_client.get(url).json()["rating"] == 5  # untouched by a tags-only update

    assert db_client.patch(url, json={"rating": 9}).status_code == 422
    assert db_client.patch(url, json={"tags": ["   "]}).status_code == 422
    missing = "/api/v1/assets/00000000-0000-0000-0000-000000000000"
    assert db_client.patch(missing, json={"rating": 1}).status_code == 404


def test_bulk_update(db_client: TestClient) -> None:
    ids = _seed(db_client)
    rome = [ids["colosseum.jpg"], ids["forum.jpg"]]
    resp = db_client.post(
        "/api/v1/assets/bulk",
        json={
            "asset_ids": [*rome, "00000000-0000-0000-0000-000000000000"],
            "rating": 3,
            "add_tags": ["Italy", "trip"],
        },
    )
    assert resp.json() == {"updated": 2}
    # Adding again is idempotent.
    db_client.post("/api/v1/assets/bulk", json={"asset_ids": rome, "add_tags": ["italy"]})
    assert _names(db_client, tag="italy", min_rating=3) == ["forum.jpg", "colosseum.jpg"]

    db_client.post(
        "/api/v1/assets/bulk", json={"asset_ids": [ids["forum.jpg"]], "remove_tags": ["TRIP"]}
    )
    facets = {
        f["value"]: f["count"] for f in db_client.get("/api/v1/library/facets").json()["tags"]
    }
    assert facets == {"Italy": 2, "trip": 1}
    assert db_client.post("/api/v1/assets/bulk", json={"asset_ids": []}).status_code == 422


def test_facets(db_client: TestClient) -> None:
    _seed(db_client)
    facets = db_client.get("/api/v1/library/facets").json()
    assert facets["total"] == 4
    assert facets["cameras"] == [
        {"value": "EOS R6", "count": 2},
        {"value": "iPhone 15", "count": 1},
    ]
    assert facets["years"] == [{"value": "2024", "count": 2}, {"value": "2023", "count": 2}]


def test_albums_crud_membership_and_cover(db_client: TestClient) -> None:
    ids = _seed(db_client)
    created = db_client.post(
        "/api/v1/albums",
        json={"name": "  Rome 2023 ", "asset_ids": [ids["forum.jpg"], ids["colosseum.jpg"]]},
    )
    assert created.status_code == 201, created.text
    album = created.json()
    assert album["name"] == "Rome 2023"
    assert album["asset_count"] == 2
    assert album["created_by"] == "dev"
    assert album["cover_asset_id"] == ids["forum.jpg"]  # first added

    url = f"/api/v1/albums/{album['id']}"
    added = db_client.post(
        f"{url}/assets", json={"asset_ids": [ids["forum.jpg"], ids["beach_day.jpg"]]}
    ).json()
    assert added["asset_count"] == 3
    assert _names(db_client, album_id=album["id"]) == [
        "beach_day.jpg",
        "forum.jpg",
        "colosseum.jpg",
    ]
    detail = db_client.get(f"/api/v1/assets/{ids['forum.jpg']}").json()
    assert detail["albums"] == [{"id": album["id"], "name": "Rome 2023"}]

    patched = db_client.patch(
        url, json={"name": "Rome", "description": "Spring", "cover_asset_id": ids["colosseum.jpg"]}
    ).json()
    assert (patched["name"], patched["description"]) == ("Rome", "Spring")
    assert patched["cover_asset_id"] == ids["colosseum.jpg"]
    outside = db_client.patch(url, json={"cover_asset_id": ids["clip.mp4"]})
    assert outside.status_code == 422

    removed = db_client.post(
        f"{url}/assets/remove", json={"asset_ids": [ids["colosseum.jpg"], ids["beach_day.jpg"]]}
    ).json()
    assert removed["asset_count"] == 1
    assert removed["cover_asset_id"] == ids["forum.jpg"]  # explicit cover left: back to auto

    assert [a["name"] for a in db_client.get("/api/v1/albums").json()] == ["Rome"]
    assert db_client.delete(url).status_code == 204
    assert db_client.get(url).status_code == 404
    # Deleting an album never deletes media.
    assert db_client.get("/api/v1/assets").json()["total"] == 4
    assert db_client.post("/api/v1/albums", json={"name": " "}).status_code == 422


@pytest.mark.parametrize(
    ("path", "patterns", "excluded"),
    [
        ("2024/@eaDir/x.jpg", ["@eadir"], True),
        ("a/b/Thumbs/x.jpg", ["thumbs"], True),
        ("a/b/x.tmp.jpg", ["*.tmp.jpg"], True),
        ("Private/2019/x.jpg", ["private/2019*"], True),
        ("Private/2019", ["Private/2019*"], True),
        ("Other/Private/2019/x.jpg", ["Private/2019*"], False),
        ("2024/x.jpg", ["2023"], False),
        ("2024/x.jpg", [], False),
    ],
)
def test_is_excluded(path: str, patterns: list[str], excluded: bool) -> None:
    assert is_excluded(path, patterns) is excluded


def test_normalise_exclude_patterns() -> None:
    assert normalise_exclude_patterns([" Private\\Old/ ", "", "@eaDir", "@EADIR"]) == [
        "Private/Old",
        "@eaDir",
    ]
    with pytest.raises(ValueError):
        normalise_exclude_patterns(["a/../b"])


def test_root_settings_and_relocation(db_client: TestClient) -> None:
    root = _register(db_client)
    url = f"/api/v1/storage-roots/{root['id']}"
    updated = db_client.patch(url, json={"label": "Family", "exclude_patterns": ["Tmp", "tmp"]})
    assert updated.status_code == 200, updated.text
    assert (updated.json()["label"], updated.json()["exclude_patterns"]) == ("Family", ["Tmp"])
    assert db_client.patch(url, json={"exclude_patterns": ["../x"]}).status_code == 422

    other = _register(db_client, path="D:/Other")
    moved = db_client.patch(
        f"/api/v1/worker/storage-roots/{root['id']}", json={"path": "E:/Photos", "volume_id": "AB"}
    )
    assert moved.status_code == 200, moved.text
    assert (moved.json()["path"], moved.json()["volume_id"]) == ("E:/Photos", "AB")
    clash = db_client.patch(
        f"/api/v1/worker/storage-roots/{other['id']}", json={"path": "E:/Photos"}
    )
    assert clash.status_code == 409


Image = pytest.importorskip("PIL.Image")


def _scan(db_client: TestClient, root_id: str) -> dict:
    from fotomind.workers.scanner import run_scan_job
    from tests.unit.test_worker_scan import _worker

    api, settings = _worker(db_client)
    api.queue_scan(root_id)
    return run_scan_job(api, settings, "pc:1", api.claim("pc", "pc:1"))


def test_exclusions_skip_folders_and_drop_catalogued_files(
    db_client: TestClient, tmp_path: Path
) -> None:
    from fotomind.workers.api import WorkerApi

    lib = tmp_path / "Photos"
    for folder in ("keep", "Private/2019", "Other/Private/2019"):
        (lib / folder).mkdir(parents=True)
    Image.new("RGB", (8, 8), "red").save(lib / "keep" / "a.jpg")
    Image.new("RGB", (8, 8), "green").save(lib / "Private" / "2019" / "b.jpg")
    Image.new("RGB", (8, 8), "blue").save(lib / "Other" / "Private" / "2019" / "c.jpg")
    Image.new("RGB", (8, 8), "white").save(lib / "keep" / "d.edit.jpg")
    root = WorkerApi(db_client).register_root("pc", str(lib), "Photos", None)

    assert _scan(db_client, root["id"])["result"]["files"] == 4
    db_client.patch(
        f"/api/v1/storage-roots/{root['id']}",
        json={"exclude_patterns": ["Private/2019*", "*.edit.jpg"]},
    )
    done = _scan(db_client, root["id"])
    assert done["status"] == "succeeded", done
    assert done["result"]["files"] == 2
    assert done["result"]["excluded"] == 2
    assert done["result"]["missing"] == 0
    assert sorted(_names(db_client)) == ["a.jpg", "c.jpg"]


def test_tiff_16_bit_greyscale_thumbnail(tmp_path: Path) -> None:
    import io

    from fotomind.workers import media

    path = tmp_path / "scan.tif"
    img = Image.new("I;16", (40, 20))
    img.putdata([i * 1000 for i in range(40)] * 20)
    img.save(path)
    kind = media.kind_for(path)
    assert kind is not None and kind.mime_type == "image/tiff"
    out = media.extract(path, kind, size_px=64)
    assert (out.width, out.height) == (40, 20)
    assert out.thumbnail is not None
    with Image.open(io.BytesIO(out.thumbnail)) as thumb:
        low, high = thumb.convert("L").getextrema()
        assert low < 30 and high > 220  # scaled, not clipped to white


def test_video_bitrate_and_audio(tmp_path: Path) -> None:
    av = pytest.importorskip("av")
    import numpy as np

    from fotomind.workers import media

    path = tmp_path / "clip.mp4"
    with av.open(str(path), "w") as out:
        video = out.add_stream("mpeg4", rate=10)
        video.width, video.height, video.pix_fmt = 64, 48, "yuv420p"
        audio = out.add_stream("aac", rate=44100)
        for i in range(10):
            frame = av.VideoFrame.from_ndarray(
                np.full((48, 64, 3), i * 20, dtype=np.uint8), format="rgb24"
            )
            out.mux(video.encode(frame))
        out.mux(video.encode())
        samples = np.zeros((1, 44100), dtype=np.float32)
        sound = av.AudioFrame.from_ndarray(samples, format="fltp", layout="mono")
        sound.sample_rate = 44100
        out.mux(audio.encode(sound))
        out.mux(audio.encode())

    ex = media.extract(path, media.kind_for(path), size_px=64)
    assert ex.metadata["has_audio"] is True
    assert ex.metadata["audio_codec"] == "aac"
    assert ex.metadata["bitrate_kbps"] > 0
    assert ex.thumbnail is not None
