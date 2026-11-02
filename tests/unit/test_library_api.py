import pytest
from fastapi.testclient import TestClient

from fotomind.modules.storage.paths import UnsafePathError, normalise_relative_path

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


def _report(path: str, sha: str, captured: str | None = "2024-05-01T10:00:00+00:00", **kw):
    return {
        "relative_path": path,
        "size_bytes": 1234,
        "mtime": "2024-06-01T08:00:00+00:00",
        "sha256": sha,
        "mime_type": "image/jpeg",
        "asset_type": "photo",
        "captured_at": captured,
        "width": 4000,
        "height": 3000,
        "camera_make": "Canon",
        "metadata": {"iso": 100},
        **kw,
    }


def _register(client: TestClient, path: str = "C:/Photos", host: str = "pc") -> dict:
    resp = client.post(
        "/api/v1/worker/storage-roots", json={"host": host, "path": path, "label": "Photos"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ingest(client: TestClient, root_id: str, files=(), unchanged=()) -> dict:
    resp = client.post(
        f"/api/v1/worker/storage-roots/{root_id}/ingest",
        json={"files": list(files), "unchanged": list(unchanged)},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("a\\b\\c.jpg", "a/b/c.jpg"), ("./x//y.png", "x/y.png"), ("photo.jpg", "photo.jpg")],
)
def test_normalise_relative_path(raw: str, expected: str) -> None:
    assert normalise_relative_path(raw) == expected


@pytest.mark.parametrize("raw", ["", "/etc/passwd", "C:/x.jpg", "a/../../b.jpg", "..", "a\x00b"])
def test_normalise_relative_path_rejects_escapes(raw: str) -> None:
    with pytest.raises(UnsafePathError):
        normalise_relative_path(raw)


def test_register_root_is_idempotent(db_client: TestClient) -> None:
    first = _register(db_client)
    second = _register(db_client)
    assert first["id"] == second["id"]
    assert [r["id"] for r in db_client.get("/api/v1/storage-roots").json()] == [first["id"]]


def test_ingest_list_detail_and_thumbnail(db_client: TestClient) -> None:
    root = _register(db_client)
    result = _ingest(
        db_client,
        root["id"],
        files=[
            _report("2024/old.jpg", SHA_A, captured="2024-01-01T00:00:00+00:00"),
            _report("2024/new.jpg", SHA_B, captured="2024-12-31T00:00:00+00:00"),
            _report("undated.png", SHA_C, captured=None, mime_type="image/png"),
        ],
    )
    assert all(f["needs_thumbnail"] for f in result["files"])
    new_id = next(f["asset_id"] for f in result["files"] if f["relative_path"] == "2024/new.jpg")

    put = db_client.put(f"/api/v1/worker/assets/{new_id}/thumbnail", content=JPEG)
    assert put.status_code == 200, put.text

    page = db_client.get("/api/v1/assets", params={"limit": 2}).json()
    assert page["total"] == 3
    # Undated file sorts by mtime (2024-06-01), between the two dated photos.
    assert [a["display_name"] for a in page["items"]] == ["new.jpg", "undated.png"]
    assert page["items"][0]["thumbnail_url"].startswith(f"/api/v1/assets/{new_id}/thumbnail?v=")
    assert page["items"][1]["thumbnail_url"] is None
    rest = db_client.get("/api/v1/assets", params={"cursor": page["next_cursor"]}).json()
    assert [a["display_name"] for a in rest["items"]] == ["old.jpg"]
    assert rest["next_cursor"] is None

    detail = db_client.get(f"/api/v1/assets/{new_id}").json()
    assert detail["camera_make"] == "Canon"
    assert detail["metadata"] == {"iso": 100}
    assert detail["files"][0]["relative_path"] == "2024/new.jpg"
    assert detail["files"][0]["storage_root_label"] == "Photos"

    thumb = db_client.get(page["items"][0]["thumbnail_url"])
    assert thumb.status_code == 200
    assert thumb.content == JPEG
    assert "immutable" in thumb.headers["cache-control"]
    assert db_client.get(f"/api/v1/assets/{new_id}").json()["thumbnail_url"]

    known = db_client.get(f"/api/v1/worker/storage-roots/{root['id']}/files").json()
    assert {k["relative_path"]: k["needs_thumbnail"] for k in known}["2024/new.jpg"] is False


def test_same_content_in_two_places_is_one_asset(db_client: TestClient) -> None:
    root = _register(db_client)
    result = _ingest(
        db_client, root["id"], files=[_report("a/x.jpg", SHA_A), _report("copy/x.jpg", SHA_A)]
    )
    assert len({f["asset_id"] for f in result["files"]}) == 1
    page = db_client.get("/api/v1/assets").json()
    assert page["total"] == 1
    detail = db_client.get(f"/api/v1/assets/{page['items'][0]['id']}").json()
    assert len(detail["files"]) == 2


def test_changed_content_moves_file_and_drops_orphan(db_client: TestClient) -> None:
    root = _register(db_client)
    first = _ingest(db_client, root["id"], files=[_report("x.jpg", SHA_A)])
    old_asset = first["files"][0]["asset_id"]
    second = _ingest(db_client, root["id"], files=[_report("x.jpg", SHA_B)])
    assert second["files"][0]["asset_id"] != old_asset
    assert second["orphaned_asset_ids"] == [old_asset]
    assert db_client.get(f"/api/v1/assets/{old_asset}").status_code == 404


def test_unsafe_paths_are_rejected(db_client: TestClient) -> None:
    root = _register(db_client)
    resp = db_client.post(
        f"/api/v1/worker/storage-roots/{root['id']}/ingest",
        json={"files": [_report("../outside.jpg", SHA_A)]},
    )
    assert resp.status_code == 422


def test_thumbnail_must_be_small_jpeg(db_client: TestClient) -> None:
    root = _register(db_client)
    asset_id = _ingest(db_client, root["id"], files=[_report("x.jpg", SHA_A)])["files"][0][
        "asset_id"
    ]
    url = f"/api/v1/worker/assets/{asset_id}/thumbnail"
    assert db_client.put(url, content=b"\x89PNG....").status_code == 422
    huge = JPEG + b"0" * (3 * 1024 * 1024)
    assert db_client.put(url, content=huge).status_code == 413


def _claim(client: TestClient, worker: str = "pc:1", host: str = "pc"):
    return client.post("/api/v1/worker/jobs/claim", json={"host": host, "worker_id": worker})


def test_scan_job_lifecycle_marks_unseen_files_missing(db_client: TestClient) -> None:
    root = _register(db_client)
    _ingest(db_client, root["id"], files=[_report("keep.jpg", SHA_A), _report("gone.jpg", SHA_B)])

    job = db_client.post(f"/api/v1/storage-roots/{root['id']}/scan")
    assert job.status_code == 202
    again = db_client.post(f"/api/v1/storage-roots/{root['id']}/scan").json()
    assert again["id"] == job.json()["id"]  # one active scan per root

    assert _claim(db_client, host="other-pc").status_code == 204
    claimed = _claim(db_client).json()
    assert claimed["status"] == "running"
    assert _claim(db_client, worker="pc:2").status_code == 204

    ack = db_client.post(
        f"/api/v1/worker/jobs/{claimed['id']}/progress",
        json={"worker_id": "pc:1", "done": 1, "total": 2},
    )
    assert ack.json() == {"cancel_requested": False}
    stranger = db_client.post(
        f"/api/v1/worker/jobs/{claimed['id']}/progress", json={"worker_id": "pc:2", "done": 1}
    )
    assert stranger.status_code == 409

    _ingest(db_client, root["id"], unchanged=["keep.jpg"])
    done = db_client.post(
        f"/api/v1/worker/jobs/{claimed['id']}/complete",
        json={"worker_id": "pc:1", "succeeded": True, "result": {"files": 1}},
    ).json()
    assert done["status"] == "succeeded"
    assert done["result"] == {"files": 1, "missing": 1}

    states = {
        a["display_name"]: a["availability"]
        for a in db_client.get("/api/v1/assets").json()["items"]
    }
    assert states == {"keep.jpg": "online", "gone.jpg": "missing"}
    roots = db_client.get("/api/v1/storage-roots").json()
    assert roots[0]["missing_count"] == 1
    assert roots[0]["last_scan_at"] is not None


def test_cancelled_scan_never_marks_files_missing(db_client: TestClient) -> None:
    root = _register(db_client)
    _ingest(db_client, root["id"], files=[_report("a.jpg", SHA_A)])
    db_client.post(f"/api/v1/storage-roots/{root['id']}/scan")
    job = _claim(db_client).json()
    assert db_client.post(f"/api/v1/jobs/{job['id']}/cancel").json()["status"] == "cancelled"
    ack = db_client.post(
        f"/api/v1/worker/jobs/{job['id']}/progress", json={"worker_id": "pc:1", "done": 0}
    )
    assert ack.json() == {"cancel_requested": True}
    db_client.post(
        f"/api/v1/worker/jobs/{job['id']}/complete",
        json={"worker_id": "pc:1", "succeeded": True},
    )
    assert db_client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == "cancelled"
    assert db_client.get("/api/v1/assets").json()["items"][0]["availability"] == "online"


def test_unreachable_root_goes_offline_not_missing(db_client: TestClient) -> None:
    root = _register(db_client)
    _ingest(db_client, root["id"], files=[_report("a.jpg", SHA_A)])
    db_client.post(f"/api/v1/storage-roots/{root['id']}/scan")
    job = _claim(db_client).json()
    db_client.post(
        f"/api/v1/worker/jobs/{job['id']}/complete",
        json={"worker_id": "pc:1", "succeeded": False, "error": "x", "root_offline": True},
    )
    assert db_client.get("/api/v1/storage-roots").json()[0]["availability"] == "offline"
    assert db_client.get("/api/v1/assets").json()["items"][0]["availability"] == "offline"


def test_bad_cursor_is_400(db_client: TestClient) -> None:
    assert db_client.get("/api/v1/assets", params={"cursor": "%%%"}).status_code == 400


def test_worker_endpoints_need_token_in_production(db_app_factory) -> None:
    headers = {"Remote-User": "family"}
    with TestClient(db_app_factory(app_env="production")) as c:
        resp = c.get("/api/v1/worker/storage-roots", params={"host": "pc"}, headers=headers)
        assert resp.status_code == 403
        assert c.get("/api/v1/assets", headers=headers).status_code == 200
    with TestClient(db_app_factory(app_env="production", worker_token="s3cret")) as c:
        url, params = "/api/v1/worker/storage-roots", {"host": "pc"}
        wrong = {**headers, "X-FotoMind-Worker-Token": "nope"}
        right = {**headers, "X-FotoMind-Worker-Token": "s3cret"}
        assert c.get(url, params=params, headers=wrong).status_code == 403
        assert c.get(url, params=params, headers=right).status_code == 200
        assert (
            c.get(url, params=params, headers={"X-FotoMind-Worker-Token": "s3cret"}).status_code
            == 401
        )


def test_library_without_database_is_503(client: TestClient) -> None:
    assert client.get("/api/v1/assets").status_code == 503


def test_cursor_roundtrip_keeps_order_with_equal_timestamps(db_client: TestClient) -> None:
    root = _register(db_client)
    same = "2024-01-01T00:00:00+00:00"
    files = [_report(f"p{i}.jpg", f"{i:064x}", captured=same) for i in range(5)]
    _ingest(db_client, root["id"], files=files)
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = db_client.get("/api/v1/assets", params=params).json()
        seen += [a["id"] for a in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 5
