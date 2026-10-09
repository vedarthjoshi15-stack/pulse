import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api import monitors, results
from app.db import Base, SessionLocal, engine
from app.services.checker import worker_loop

Base.metadata.create_all(bind=engine)  # Alembic migrations replace this later


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if os.getenv("ENABLE_WORKER", "1") == "1":
        task = asyncio.create_task(worker_loop(SessionLocal))
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Pulse", lifespan=lifespan)
app.include_router(monitors.router)
app.include_router(results.router)


@app.get("/health")
def health():
    return {"status": "ok"}
