import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import tables
from app.api import create_app
from app.seed import seed


@pytest.fixture(scope="session")
def client() -> TestClient:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        tables.metadata.create_all(conn)
        seed(conn)
    return TestClient(create_app(engine))
