import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_get_monitor(client):
    res = client.post("/monitors", json={"name": "Google", "url": "https://google.com"})
    assert res.status_code == 201
    monitor_id = res.json()["id"]

    fetched = client.get(f"/monitors/{monitor_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Google"
    assert len(client.get("/monitors").json()) == 1


def test_rejects_invalid_url(client):
    res = client.post("/monitors", json={"name": "Bad", "url": "not-a-url"})
    assert res.status_code == 422


def test_missing_monitor_returns_404(client):
    assert client.get("/monitors/999").status_code == 404
