from fastapi import FastAPI

from app.api import monitors
from app.db import Base, engine

Base.metadata.create_all(bind=engine)  # Alembic migrations replace this later

app = FastAPI(title="Pulse")
app.include_router(monitors.router)


@app.get("/health")
def health():
    return {"status": "ok"}
