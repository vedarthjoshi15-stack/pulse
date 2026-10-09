from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Monitor
from app.schemas import MonitorCreate, MonitorOut

router = APIRouter(prefix="/monitors", tags=["monitors"])


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
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return monitor
