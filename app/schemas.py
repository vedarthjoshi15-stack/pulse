from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: HttpUrl
    interval_seconds: int = Field(default=60, ge=10, le=3600)


class MonitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    interval_seconds: int
    is_active: bool
    created_at: datetime


class CheckResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    monitor_id: int
    status_code: int | None
    response_ms: float | None
    is_up: bool
    error: str | None
    checked_at: datetime


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    monitor_id: int
    started_at: datetime
    resolved_at: datetime | None


class UptimeOut(BaseModel):
    monitor_id: int
    window_hours: int
    total_checks: int
    uptime_percent: float | None
    avg_response_ms: float | None


class MonitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: HttpUrl | None = None
    interval_seconds: int | None = Field(default=None, ge=10, le=3600)
    is_active: bool | None = None
