import pytest

from tests.conftest import make_settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgres://u:p@192.168.1.129:5432/fotomind",
            "postgresql+psycopg://u:p@192.168.1.129:5432/fotomind",
        ),
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ],
)
def test_database_url_is_normalised_for_psycopg(raw: str, expected: str) -> None:
    settings = make_settings(database_url=raw)
    assert settings.database_url is not None
    assert settings.database_url.get_secret_value() == expected


def test_empty_database_url_means_unconfigured() -> None:
    assert make_settings(database_url="").database_url is None


def test_database_url_is_not_leaked_in_repr() -> None:
    settings = make_settings(database_url="postgres://u:secret@h/db")
    assert "secret" not in repr(settings)


def test_cors_origins_accept_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a, http://b")
    assert make_settings().cors_origins == ["http://a", "http://b"]
