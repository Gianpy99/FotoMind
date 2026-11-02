from fastapi.testclient import TestClient


def test_portal_health_ok_without_database_outside_production(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_portal_health_fails_in_production_without_database(app_factory) -> None:
    with TestClient(app_factory(app_env="production")) as c:
        resp = c.get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "unavailable"


def test_portal_health_needs_no_login_in_production(app_factory) -> None:
    unreachable = "postgres://u:p@127.0.0.1:1/none"
    app = app_factory(
        app_env="production", database_url=unreachable, run_migrations_on_startup=False
    )
    with TestClient(app) as c:
        resp = c.get("/health")
    # Not 401: the probe works without Remote-User; it reports the DB as unavailable.
    assert resp.status_code == 503


def test_api_liveness(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_system_status_reports_unconfigured_database(client: TestClient) -> None:
    resp = client.get("/api/v1/system/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"]["status"] == "unconfigured"


def test_openapi_contract_is_served(client: TestClient) -> None:
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    assert "/api/v1/me" in resp.json()["paths"]
