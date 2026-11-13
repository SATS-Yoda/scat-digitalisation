"""Tests run on in-memory SQLite by default. Set TEST_ON_POSTGRES=1 to run them on the
dedicated `scat_console_dev` database of the server in DATABASE_URL; that database is
wiped and re-seeded for every test, and no other database is ever touched."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.pool import StaticPool

from app import tables
from app.api import create_app
from app.dify import SapSendResult
from app.seed import DEV_DATABASE, is_disposable, seed

ON_POSTGRES = os.environ.get("TEST_ON_POSTGRES") == "1"


@pytest.fixture(scope="session")
def postgres_engine():
    from app.config import Settings

    url = make_url(Settings().database_url).set(database=DEV_DATABASE)
    url = url.update_query_dict({"sslmode": "require"})
    assert is_disposable(url)
    engine = create_engine(url)
    with engine.begin() as conn:
        tables.metadata.drop_all(conn)
        tables.metadata.create_all(conn)
    yield engine
    engine.dispose()


@pytest.fixture
def engine(request):
    if ON_POSTGRES:
        engine = request.getfixturevalue("postgres_engine")
        names = ", ".join(t.name for t in tables.metadata.sorted_tables)
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
            seed(conn)
        return engine
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        tables.metadata.create_all(conn)
        seed(conn)
    return engine


class FakeSapSender:
    """Stands in for the Dify SAP-send workflow. Tests never call the real one."""

    def __init__(self):
        self.calls: list[dict] = []
        self.result = SapSendResult(
            i033_uploaded=True,
            i033_file_name="I033_SYNTHETIC.dat",
            i034_uploaded=True,
            i034_file_name="I034_SYNTHETIC.dat",
            run_id="synthetic-run",
        )
        self.before_return = lambda: None

    def __call__(self, inputs: dict, user_id: str) -> SapSendResult:
        self.calls.append(inputs)
        self.before_return()
        return self.result


@pytest.fixture
def sender() -> FakeSapSender:
    return FakeSapSender()


@pytest.fixture
def app(engine, sender):
    return create_app(engine, sender)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)
