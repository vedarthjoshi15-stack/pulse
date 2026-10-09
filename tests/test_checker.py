import asyncio

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import CheckResult, Incident, Monitor
from app.services.checker import check_url, record_result, run_checks_once


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()


def _check(handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await check_url(client, "https://example.com")

    return asyncio.run(go())


def test_check_url_up():
    result = _check(lambda req: httpx.Response(200))
    assert result["is_up"] is True
    assert result["status_code"] == 200
    assert result["response_ms"] is not None


def test_check_url_down_on_500():
    result = _check(lambda req: httpx.Response(500))
    assert result["is_up"] is False
    assert result["status_code"] == 500


def test_check_url_down_on_network_error():
    def boom(request):
        raise httpx.ConnectError("boom", request=request)

    result = _check(boom)
    assert result["is_up"] is False
    assert result["error"] == "ConnectError"


def test_incident_opens_once_and_resolves(session_factory):
    down = {"status_code": 500, "response_ms": 5.0, "is_up": False, "error": None}
    up = {"status_code": 200, "response_ms": 5.0, "is_up": True, "error": None}

    with session_factory() as db:
        db.add(Monitor(name="m", url="https://example.com"))
        db.commit()

        assert record_result(db, 1, down) == "opened"
        assert record_result(db, 1, down) is None  # still the same incident
        assert len(db.scalars(select(Incident)).all()) == 1

        assert record_result(db, 1, up) == "resolved"
        assert db.scalars(select(Incident)).first().resolved_at is not None


def test_run_checks_respects_interval(session_factory):
    async def go():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200))
        ) as client:
            first = await run_checks_once(session_factory, client)
            second = await run_checks_once(session_factory, client)
            return first, second

    with session_factory() as db:
        db.add(Monitor(name="m", url="https://example.com", interval_seconds=60))
        db.commit()

    assert asyncio.run(go()) == (1, 0)  # second run: not due yet
    with session_factory() as db:
        assert len(db.scalars(select(CheckResult)).all()) == 1
