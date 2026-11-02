from pathlib import Path

from fastapi.testclient import TestClient


def _dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>fotomind</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    return dist


def test_spa_serves_index_assets_and_fallback(app_factory, tmp_path: Path) -> None:
    with TestClient(app_factory(web_dist_dir=_dist(tmp_path))) as c:
        assert "fotomind" in c.get("/").text
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert "fotomind" in c.get("/library/some/deep/link").text


def test_spa_does_not_escape_dist_or_shadow_api(app_factory, tmp_path: Path) -> None:
    with TestClient(app_factory(web_dist_dir=_dist(tmp_path))) as c:
        assert "nope" not in c.get("/../secret.txt").text
        assert "nope" not in c.get("/%2e%2e/secret.txt").text
        assert c.get("/api/v1/does-not-exist").status_code == 404
        assert c.get("/health").json()["status"] == "ok"
