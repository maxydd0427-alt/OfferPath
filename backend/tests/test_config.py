from app.core.config import get_database_backend


def test_database_backend_detection() -> None:
    assert get_database_backend("sqlite:///./offerpath.db") == "sqlite"
    assert get_database_backend("postgresql://user:pass@localhost:5432/db") == "postgresql"
    assert (
        get_database_backend("postgresql+psycopg://user:pass@localhost:5432/db")
        == "postgresql"
    )
    assert get_database_backend("mysql://user:pass@localhost:3306/db") == "unknown"
