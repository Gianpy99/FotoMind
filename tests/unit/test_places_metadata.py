"""Locations, the map and metadata edits (LIB-007/008)."""

from fastapi.testclient import TestClient

from fotomind.modules import places
from tests.unit.test_library_api import _ingest, _register, _report

SHAS = [f"{i:x}" * 64 for i in range(1, 5)]


def _seed(client: TestClient) -> tuple[str, dict[str, str]]:
    root = _register(client)
    files = [
        _report(
            "gps.jpg",
            SHAS[0],
            captured="2024-01-01T10:00:00+00:00",
            latitude=48.8566,
            longitude=2.3522,
        ),
        _report("tagged.jpg", SHAS[1], captured="2024-01-02T10:00:00+00:00"),
        _report("plain.jpg", SHAS[2], captured="2024-01-03T10:00:00+00:00", camera_model="EOS R6"),
    ]
    result = _ingest(client, root["id"], files=files)
    return root["id"], {f["relative_path"]: f["asset_id"] for f in result["files"]}


def _asset(client: TestClient, asset_id: str) -> dict:
    resp = client.get(f"/api/v1/assets/{asset_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_gazetteer_lookup_search_nearest() -> None:
    rome = places.lookup("Roma")[0]
    assert (rome.name, rome.country_code) == ("Rome", "IT")
    assert places.lookup("italy")[0].kind == "country"
    assert places.search("firen")[0].name == "Florence"
    near = places.nearest(41.9, 12.48)
    assert near is not None and near.name == "Rome"
    assert places.nearest(0.0, -30.0) is None  # mid-Atlantic
    assert places.lookup("birthday") == []


def test_file_position_and_near_label(db_client: TestClient) -> None:
    _, ids = _seed(db_client)
    gps = _asset(db_client, ids["gps.jpg"])
    assert gps["location"] == {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "source": "file",
        "label": None,
        "tag": None,
    }
    assert gps["location_near"].startswith("Paris")
    facets = db_client.get("/api/v1/library/facets").json()
    assert facets["located"] == 1
    located = db_client.get("/api/v1/assets", params={"located": True}).json()
    assert [a["display_name"] for a in located["items"]] == ["gps.jpg"]
    unlocated = db_client.get("/api/v1/assets", params={"located": False}).json()
    assert unlocated["total"] == 2


def test_place_tag_confirm_puts_photos_on_the_map(db_client: TestClient) -> None:
    _, ids = _seed(db_client)
    db_client.patch(f"/api/v1/assets/{ids['tagged.jpg']}", json={"tags": ["Roma", "Family"]})

    tags = db_client.get("/api/v1/places/tags").json()
    assert [s["tag"] for s in tags["suggestions"]] == ["Roma"]  # "Family" is not a place
    rome = tags["suggestions"][0]["candidates"][0]
    assert rome["label"].startswith("Rome")

    resp = db_client.put(
        "/api/v1/places/tags",
        json={"tag": "roma", "status": "confirmed", "place": {**rome, "kind": "city"}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["suggestions"] == []
    assert resp.json()["decided"][0]["status"] == "confirmed"

    tagged = _asset(db_client, ids["tagged.jpg"])
    assert tagged["location"]["source"] == "tag"
    assert tagged["location"]["tag"] == "Roma"

    points = db_client.get("/api/v1/map/assets").json()
    assert {p["display_name"]: p["source"] for p in points["items"]} == {
        "gps.jpg": "file",
        "tagged.jpg": "tag",
    }
    assert points["truncated"] is False
    filtered = db_client.get("/api/v1/map/assets", params={"tag": "Roma"}).json()
    assert [p["display_name"] for p in filtered["items"]] == ["tagged.jpg"]

    # The decision survives the tag being removed from every photo.
    db_client.patch(f"/api/v1/assets/{ids['tagged.jpg']}", json={"tags": []})
    assert db_client.get("/api/v1/places/tags").json()["decided"][0]["tag"] == "Roma"

    bad = db_client.put("/api/v1/places/tags", json={"tag": "Roma", "status": "confirmed"})
    assert bad.status_code == 422
    missing = db_client.put("/api/v1/places/tags", json={"tag": "nope", "status": "rejected"})
    assert missing.status_code == 404


def test_rejected_tag_is_not_suggested(db_client: TestClient) -> None:
    _, ids = _seed(db_client)
    db_client.patch(f"/api/v1/assets/{ids['plain.jpg']}", json={"tags": ["Florence"]})
    db_client.put("/api/v1/places/tags", json={"tag": "Florence", "status": "rejected"})
    tags = db_client.get("/api/v1/places/tags").json()
    assert tags["suggestions"] == []
    assert tags["decided"][0]["status"] == "rejected"
    assert db_client.get("/api/v1/map/assets").json()["items"][0]["display_name"] == "gps.jpg"


def test_bulk_metadata_edit_and_revert(db_client: TestClient) -> None:
    root_id, ids = _seed(db_client)
    selection = [ids["gps.jpg"], ids["plain.jpg"]]
    resp = db_client.post(
        "/api/v1/assets/bulk",
        json={
            "asset_ids": selection,
            "metadata": {
                "title": "Trip",
                "shift_seconds": 3600,
                "location": {"latitude": 43.7696, "longitude": 11.2558, "label": "Florence"},
                "camera_model": "X100V",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 2

    gps = _asset(db_client, ids["gps.jpg"])
    assert gps["title"] == "Trip"
    assert gps["captured_at"].startswith("2024-01-01T11:00:00")  # each shifted by an hour
    assert gps["location"]["source"] == "manual"
    assert gps["location"]["label"] == "Florence"
    assert gps["camera_model"] == "X100V"
    assert sorted(gps["edited_fields"]) == ["camera_model", "captured_at", "location"]
    assert gps["file_values"]["location"] == {"latitude": 48.8566, "longitude": 2.3522}
    plain = _asset(db_client, ids["plain.jpg"])
    assert plain["captured_at"].startswith("2024-01-03T11:00:00")
    assert db_client.get("/api/v1/assets", params={"q": "trip"}).json()["total"] == 2
    assert db_client.get("/api/v1/assets", params={"q": "florence"}).json()["total"] == 2

    # A rescan reports what the file says but keeps the user's edits.
    rescan = _report(
        "gps.jpg", SHAS[0], captured="2024-01-01T10:00:00+00:00", latitude=1.5, longitude=2.5
    )
    _ingest(db_client, root_id, files=[rescan])
    gps = _asset(db_client, ids["gps.jpg"])
    assert gps["location"]["latitude"] == 43.7696
    assert gps["file_values"]["location"] == {"latitude": 1.5, "longitude": 2.5}

    resp = db_client.patch(
        f"/api/v1/assets/{ids['gps.jpg']}",
        json={"metadata": {"revert": ["location", "captured_at"], "title": ""}},
    )
    assert resp.status_code == 200, resp.text
    gps = resp.json()
    assert gps["title"] is None
    assert gps["location"]["latitude"] == 1.5
    assert gps["location"]["source"] == "file"
    assert gps["captured_at"].startswith("2024-01-01T10:00:00")
    assert gps["edited_fields"] == ["camera_model"]


def test_clear_location_hides_tag_position(db_client: TestClient) -> None:
    _, ids = _seed(db_client)
    db_client.patch(f"/api/v1/assets/{ids['plain.jpg']}", json={"tags": ["Rome"]})
    rome = places.lookup("Rome")[0]
    db_client.put(
        "/api/v1/places/tags",
        json={
            "tag": "Rome",
            "status": "confirmed",
            "place": {"latitude": rome.latitude, "longitude": rome.longitude, "label": rome.label},
        },
    )
    assert _asset(db_client, ids["plain.jpg"])["location"]["source"] == "tag"
    db_client.post(
        "/api/v1/assets/bulk",
        json={
            "asset_ids": [ids["plain.jpg"], ids["gps.jpg"]],
            "metadata": {"clear_location": True},
        },
    )
    assert _asset(db_client, ids["plain.jpg"])["location"] is None
    assert db_client.get("/api/v1/map/assets").json()["items"] == []
    assert db_client.get("/api/v1/library/facets").json()["located"] == 0


def test_invalid_metadata_edits_are_rejected(db_client: TestClient) -> None:
    _, ids = _seed(db_client)
    url = f"/api/v1/assets/{ids['plain.jpg']}"
    for bad in (
        {"captured_at": "2024-01-01T00:00:00Z", "shift_seconds": 60},
        {"location": {"latitude": 1, "longitude": 2}, "clear_location": True},
        {"location": {"latitude": 91, "longitude": 2}},
        {"camera_model": "X", "revert": ["camera_model"]},
        {"revert": ["rating"]},
    ):
        assert db_client.patch(url, json={"metadata": bad}).status_code == 422, bad


def test_place_search_endpoint(db_client: TestClient) -> None:
    resp = db_client.get("/api/v1/places/search", params={"q": "sao pa"})
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "São Paulo"
