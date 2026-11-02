from fastapi.testclient import TestClient

PORTAL_HEADERS = {"Remote-User": "gianpaolo", "Remote-Groups": "family, admins"}


def test_portal_headers_identify_the_user(app_factory) -> None:
    with TestClient(app_factory(app_env="production")) as c:
        resp = c.get("/api/v1/me", headers=PORTAL_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == {"username": "gianpaolo", "groups": ["family", "admins"]}


def test_production_without_remote_user_is_401(app_factory) -> None:
    with TestClient(app_factory(app_env="production", dev_user="dev")) as c:
        resp = c.get("/api/v1/me")
    assert resp.status_code == 401


def test_dev_user_fallback_outside_production(client: TestClient) -> None:
    resp = client.get("/api/v1/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "dev"


def test_dev_without_dev_user_is_401(app_factory) -> None:
    with TestClient(app_factory(dev_user=None)) as c:
        assert c.get("/api/v1/me").status_code == 401
