from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CheckResult, Incident, Monitor
from app.schemas import MonitorCreate, MonitorOut, MonitorUpdate

router = APIRouter(prefix="/monitors", tags=["monitors"])


def _get_or_404(db: Session, monitor_id: int) -> Monitor:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor


@router.post("", response_model=MonitorOut, status_code=201)
def create_monitor(payload: MonitorCreate, db: Session = Depends(get_db)):
    monitor = Monitor(
        name=payload.name,
        url=str(payload.url),
        interval_seconds=payload.interval_seconds,
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return monitor


@router.get("", response_model=list[MonitorOut])
def list_monitors(db: Session = Depends(get_db)):
    return db.scalars(select(Monitor).order_by(Monitor.id)).all()


@router.get("/{monitor_id}", response_model=MonitorOut)
def get_monitor(monitor_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, monitor_id)


@router.patch("/{monitor_id}", response_model=MonitorOut)
def update_monitor(
    monitor_id: int, payload: MonitorUpdate, db: Session = Depends(get_db)
):
    monitor = _get_or_404(db, monitor_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        setattr(monitor, field, str(value) if field == "url" else value)
    db.commit()
    db.refresh(monitor)
    return monitor


@router.delete("/{monitor_id}", status_code=204)
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)):
    monitor = _get_or_404(db, monitor_id)
    db.execute(delete(CheckResult).where(CheckResult.monitor_id == monitor_id))
    db.execute(delete(Incident).where(Incident.monitor_id == monitor_id))
    db.delete(monitor)
    db.commit()
    return Response(status_code=204)
