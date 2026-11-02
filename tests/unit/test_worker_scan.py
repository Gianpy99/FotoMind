import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fotomind.workers import media
from fotomind.workers.api import WorkerApi
from fotomind.workers.config import WorkerSettings
from fotomind.workers.scanner import iter_media, run_scan_job

Image = pytest.importorskip("PIL.Image")


def _jpeg_with_exif(path: Path, when: str, orientation: int = 1) -> None:
    img = Image.new("RGB", (64, 32), (200, 30, 30))
    exif = Image.Exif()
    exif[271] = "Canon\x00"
    exif[272] = "EOS R6"
    exif[274] = orientation
    sub = exif.get_ifd(0x8769)
    sub[36867] = when
    sub[36881] = "+02:00"
    sub[34855] = 400
    img.save(path, "JPEG", exif=exif)


@pytest.fixture
def library(tmp_path: Path) -> Path:
    root = tmp_path / "Photos"
    (root / "2024" / "trip").mkdir(parents=True)
    (root / ".hidden").mkdir()
    _jpeg_with_exif(root / "2024" / "trip" / "beach.jpg", "2024:07:14 18:30:00", orientation=6)
    Image.new("RGBA", (40, 40), (0, 0, 255, 128)).save(root / "2024" / "logo.png")
    (root / "notes.txt").write_text("not media")
    (root / "~$lock.jpg").write_bytes(b"temp")
    _jpeg_with_exif(root / ".hidden" / "secret.jpg", "2020:01:01 00:00:00")
    return root


def test_iter_media_skips_hidden_temp_and_unsupported(library: Path) -> None:
    found = [rel for _, rel, _ in iter_media(library)]
    assert found == ["2024/logo.png", "2024/trip/beach.jpg"]


def test_extract_jpeg_reads_exif_and_orientation(library: Path) -> None:
    path = library / "2024" / "trip" / "beach.jpg"
    out = media.extract(path, media.kind_for(path), size_px=128)
    assert out.captured_at == datetime(2024, 7, 14, 18, 30, tzinfo=timezone(timedelta(hours=2)))
    assert out.camera_make == "Canon"  # NUL padding stripped
    assert (out.width, out.height) == (32, 64)  # orientation 6 swaps the axes
    assert out.metadata["iso"] == 400
    with Image.open(io.BytesIO(out.thumbnail)) as thumb:
        assert thumb.format == "JPEG"
        assert thumb.size == (32, 64)


def test_parse_exif_datetime_without_offset_assumes_local_zone() -> None:
    parsed, known = media.parse_exif_datetime("2024:01:02 03:04:05")
    assert known is False
    assert parsed is not None and parsed.tzinfo is not None
    assert media.parse_exif_datetime("garbage") == (None, False)


def _worker(client: TestClient) -> tuple[WorkerApi, WorkerSettings]:
    settings = WorkerSettings(worker_host="pc", thumbnail_px=128, batch_size=1, _env_file=None)
    return WorkerApi(client), settings


def test_scan_end_to_end_then_rescan_and_delete(db_client: TestClient, library: Path) -> None:
    api, settings = _worker(db_client)
    root = api.register_root("pc", str(library), "Photos", None)

    api.queue_scan(root["id"])
    job = api.claim("pc", "pc:1")
    done = run_scan_job(api, settings, "pc:1", job)
    assert done["status"] == "succeeded", done
    assert done["result"]["files"] == 2
    assert done["result"]["thumbnails"] == 2

    page = db_client.get("/api/v1/assets").json()
    assert page["total"] == 2
    beach = next(a for a in page["items"] if a["display_name"] == "beach.jpg")
    assert beach["captured_at"].startswith("2024-07-14T16:30:00")  # 18:30+02:00 in UTC
    assert db_client.get(beach["thumbnail_url"]).headers["content-type"] == "image/jpeg"

    # Rescan: nothing changed, so nothing is re-hashed or re-uploaded.
    api.queue_scan(root["id"])
    again = run_scan_job(api, settings, "pc:1", api.claim("pc", "pc:1"))
    assert again["result"].get("unchanged") == 2
    assert "thumbnails" not in again["result"]

    (library / "2024" / "logo.png").unlink()
    api.queue_scan(root["id"])
    third = run_scan_job(api, settings, "pc:1", api.claim("pc", "pc:1"))
    assert third["result"]["missing"] == 1
    missing = db_client.get("/api/v1/assets", params={"availability": "missing"}).json()
    assert [a["display_name"] for a in missing["items"]] == ["logo.png"]


def test_unplugged_root_marks_offline(db_client: TestClient, tmp_path: Path) -> None:
    api, settings = _worker(db_client)
    root = api.register_root("pc", str(tmp_path / "E-drive"), "External", None)
    api.queue_scan(root["id"])
    done = run_scan_job(api, settings, "pc:1", api.claim("pc", "pc:1"))
    assert done["status"] == "failed"
    assert db_client.get("/api/v1/storage-roots").json()[0]["availability"] == "offline"
