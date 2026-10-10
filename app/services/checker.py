import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import desc, select

from app.models import CheckResult, Incident, Monitor, utcnow
from app.services.alerts import send_alert

logger = logging.getLogger("pulse.checker")


async def check_url(client: httpx.AsyncClient, url: str, timeout: float = 10.0) -> dict:
    """Hit a URL once and describe what happened. Never raises on network errors."""
    start = time.perf_counter()
    try:
        resp = await client.get(url, timeout=timeout, follow_redirects=True)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "status_code": resp.status_code,
            "response_ms": elapsed_ms,
            "is_up": resp.status_code < 400,
            "error": None,
        }
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        return {
            "status_code": None,
            "response_ms": None,
            "is_up": False,
            "error": type(exc).__name__,
        }


def record_result(db, monitor_id: int, result: dict) -> str | None:
    """Store a check and manage incidents.

    Returns "opened" when a new incident starts, "resolved" when one ends,
    otherwise None.
    """
    db.add(CheckResult(monitor_id=monitor_id, **result))

    open_incident = db.scalars(
        select(Incident).where(
            Incident.monitor_id == monitor_id, Incident.resolved_at.is_(None)
        )
    ).first()

    event = None
    if not result["is_up"] and open_incident is None:
        db.add(Incident(monitor_id=monitor_id))
        event = "opened"
    elif result["is_up"] and open_incident is not None:
        open_incident.resolved_at = utcnow()
        event = "resolved"

    db.commit()
    return event


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _describe(result: dict) -> str:
    return result["error"] or f"HTTP {result['status_code']}"


async def run_checks_once(session_factory, client: httpx.AsyncClient) -> int:
    """Check every active monitor that is due, concurrently. Returns how many ran."""
    now = utcnow()
    with session_factory() as db:
        due = []
        for m in db.scalars(select(Monitor).where(Monitor.is_active.is_(True))).all():
            last = db.scalars(
                select(CheckResult.checked_at)
                .where(CheckResult.monitor_id == m.id)
                .order_by(desc(CheckResult.checked_at))
                .limit(1)
            ).first()
            if last is None or _as_utc(last) + timedelta(seconds=m.interval_seconds) <= now:
                due.append((m.id, m.name, m.url))

        results = await asyncio.gather(*(check_url(client, url) for _, _, url in due))

        for (monitor_id, name, url), result in zip(due, results):
            event = record_result(db, monitor_id, result)
            if event:
                await send_alert(client, event, name, url, _describe(result))
    return len(due)


async def worker_loop(session_factory, tick_seconds: float = 5.0) -> None:
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await run_checks_once(session_factory, client)
            except Exception:
                logger.exception("check cycle failed")
            await asyncio.sleep(tick_seconds)
