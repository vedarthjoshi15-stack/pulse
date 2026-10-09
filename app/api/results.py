from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, desc, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CheckResult, Incident, Monitor, utcnow
from app.schemas import CheckResultOut, IncidentOut, UptimeOut

router = APIRouter(prefix="/monitors", tags=["results"])


def _require_monitor(db: Session, monitor_id: int) -> None:
    if db.get(Monitor, monitor_id) is None:
        raise HTTPException(status_code=404, detail="Monitor not found")


@router.get("/{monitor_id}/results", response_model=list[CheckResultOut])
def list_results(
    monitor_id: int, limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)
):
    _require_monitor(db, monitor_id)
    return db.scalars(
        select(CheckResult)
        .where(CheckResult.monitor_id == monitor_id)
        .order_by(desc(CheckResult.checked_at))
        .limit(limit)
    ).all()


@router.get("/{monitor_id}/incidents", response_model=list[IncidentOut])
def list_incidents(monitor_id: int, db: Session = Depends(get_db)):
    _require_monitor(db, monitor_id)
    return db.scalars(
        select(Incident)
        .where(Incident.monitor_id == monitor_id)
        .order_by(desc(Incident.started_at))
    ).all()


@router.get("/{monitor_id}/uptime", response_model=UptimeOut)
def uptime(monitor_id: int, hours: int = Query(24, ge=1, le=720), db: Session = Depends(get_db)):
    _require_monitor(db, monitor_id)
    since = utcnow() - timedelta(hours=hours)
    total, up, avg_ms = db.execute(
        select(
            func.count(CheckResult.id),
            func.sum(CheckResult.is_up.cast(Integer)),
            func.avg(CheckResult.response_ms),
        ).where(CheckResult.monitor_id == monitor_id, CheckResult.checked_at >= since)
    ).one()
    return UptimeOut(
        monitor_id=monitor_id,
        window_hours=hours,
        total_checks=total,
        uptime_percent=round(100 * (up or 0) / total, 2) if total else None,
        avg_response_ms=round(avg_ms, 1) if avg_ms is not None else None,
    )
