from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import CheckResult, Incident, Monitor, utcnow


@pytest.fixture()
def env():
    """A test client plus a session factory for putting data straight into the test DB."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), Session
    app.dependency_overrides.clear()
    engine.dispose()


def _add_monitor(db):
    db.add(Monitor(name="m", url="https://example.com"))
    db.commit()


def test_results_newest_first_and_limit(env):
    client, Session = env
    now = utcnow()
    with Session() as db:
        _add_monitor(db)
        for i, code in enumerate([200, 201, 202]):
            db.add(
                CheckResult(
                    monitor_id=1,
                    status_code=code,
                    response_ms=10.0,
                    is_up=True,
                    checked_at=now - timedelta(seconds=30 - 10 * i),
                )
            )
        db.commit()

    res = client.get("/monitors/1/results?limit=2")
    assert res.status_code == 200
    assert [r["status_code"] for r in res.json()] == [202, 201]


def test_results_404_for_missing_monitor(env):
    client, _ = env
    assert client.get("/monitors/999/results").status_code == 404


def test_incidents_listed_newest_first(env):
    client, Session = env
    now = utcnow()
    with Session() as db:
        _add_monitor(db)
        db.add(
            Incident(
                monitor_id=1,
                started_at=now - timedelta(hours=1),
                resolved_at=now - timedelta(minutes=30),
            )
        )
        db.add(Incident(monitor_id=1, started_at=now - timedelta(minutes=10)))
        db.commit()

    data = client.get("/monitors/1/incidents").json()
    assert len(data) == 2
    assert data[0]["resolved_at"] is None  # newest incident is still open
    assert data[1]["resolved_at"] is not None


def test_incidents_404_for_missing_monitor(env):
    client, _ = env
    assert client.get("/monitors/999/incidents").status_code == 404


def test_uptime_calculation_ignores_old_checks(env):
    client, Session = env
    now = utcnow()
    rows = [(True, 100.0), (True, 200.0), (True, 300.0), (False, None)]
    with Session() as db:
        _add_monitor(db)
        for i, (up, ms) in enumerate(rows):
            db.add(
                CheckResult(
                    monitor_id=1,
                    status_code=200 if up else 500,
                    response_ms=ms,
                    is_up=up,
                    checked_at=now - timedelta(minutes=i + 1),
                )
            )
        # a failed check from 2 days ago: outside the 24h window, must not count
        db.add(
            CheckResult(
                monitor_id=1,
                status_code=500,
                response_ms=None,
                is_up=False,
                checked_at=now - timedelta(hours=48),
            )
        )
        db.commit()

    body = client.get("/monitors/1/uptime?hours=24").json()
    assert body["total_checks"] == 4
    assert body["uptime_percent"] == 75.0
    assert body["avg_response_ms"] == 200.0


def test_uptime_with_no_checks(env):
    client, Session = env
    with Session() as db:
        _add_monitor(db)

    body = client.get("/monitors/1/uptime").json()
    assert body["total_checks"] == 0
    assert body["uptime_percent"] is None
    assert body["avg_response_ms"] is None


def test_uptime_404_for_missing_monitor(env):
    client, _ = env
    assert client.get("/monitors/999/uptime").status_code == 404


def test_uptime_rejects_bad_window(env):
    client, Session = env
    with Session() as db:
        _add_monitor(db)
    assert client.get("/monitors/1/uptime?hours=0").status_code == 422


def test_app_starts_and_stops_with_worker_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_WORKER", "0")
    with TestClient(app) as client:  # runs startup and shutdown
        assert client.get("/health").json() == {"status": "ok"}
