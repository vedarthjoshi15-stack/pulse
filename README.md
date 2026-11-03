# Pulse

![CI](https://github.com/vedarthjoshi15-stack/pulse/actions/workflows/ci.yml/badge.svg)

Pulse is an uptime and incident monitoring API. You register URLs to watch, and Pulse checks them on a schedule, stores latency and status history, tracks incidents, and sends a Discord alert when a service goes down or recovers.

Built with Python, FastAPI, SQLAlchemy, PostgreSQL, and Docker.

## Features

- REST API to create, list, update, and delete monitors, with input validation and auto-generated OpenAPI docs
- Async checker that runs many checks concurrently, each on its own interval
- Check history with status code, response time, and error type
- Incident tracking: one incident opens when a service goes down and closes when it recovers
- Uptime percentage and average latency over a chosen time window
- Discord webhook alerts, sent only when the status changes
- PostgreSQL with Alembic migrations, Docker image, Docker Compose setup, and GitHub Actions CI

## Architecture

```mermaid
flowchart LR
    Client[API client / Swagger UI] --> API[FastAPI app]
    API --> DB[(PostgreSQL)]
    Worker[Async checker worker] --> DB
    Worker -->|HTTP GET every N seconds| Sites[Monitored websites]
    Worker -->|on down / recovery| Discord[Discord webhook]
```

The checker runs as a background task inside the API process (started in the FastAPI lifespan). Code is split into routers (`app/api`), business logic (`app/services`), models, and schemas.

## Quick start (Docker)

```bash
git clone https://github.com/vedarthjoshi15-stack/pulse.git
cd pulse
docker compose up --build
```

Open http://localhost:8000/docs. Migrations run automatically when the API container starts.

To enable Discord alerts, export a webhook URL before starting:

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
docker compose up --build
```

## API

| Method | Path | Description |
|---|---|---|
| POST | `/monitors` | Create a monitor |
| GET | `/monitors` | List monitors |
| GET | `/monitors/{id}` | Get one monitor |
| PATCH | `/monitors/{id}` | Update a monitor |
| DELETE | `/monitors/{id}` | Delete a monitor and its history |
| GET | `/monitors/{id}/results` | Check history, newest first |
| GET | `/monitors/{id}/incidents` | Incident history |
| GET | `/monitors/{id}/uptime?hours=24` | Uptime % and average latency |
| GET | `/health` | Health check |

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

docker run -d --name pulse-db -e POSTGRES_USER=pulse -e POSTGRES_PASSWORD=pulse \
  -e POSTGRES_DB=pulse -p 5432:5432 postgres:16

export DATABASE_URL="postgresql+psycopg://pulse:pulse@localhost:5432/pulse"
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

```bash
pytest --cov=app
```

Tests use in-memory SQLite and mocked HTTP, so they need no database or internet. GitHub Actions runs them on every push, fails the build if coverage drops below 80%, and also builds the Docker image.

## Design decisions

- **Async checks.** The checker uses `asyncio` and `httpx` so many slow sites are checked at the same time instead of one after another. A slow or dead site does not delay the others.
- **Incident logic as a small state machine.** A failed check opens an incident only if none is open, and a successful check closes the open one. A site that stays down creates one incident, not one per check.
- **Alerts on state changes only.** Because alerts come from incident open and close events, a long outage sends two messages, not hundreds.
- **Alert failures never stop checking.** Sending an alert catches network errors, and the logs avoid printing the webhook URL, which is a secret.
- **Secrets in environment variables.** The webhook URL and database URL are never committed.
- **Migrations with Alembic.** The schema is versioned instead of created implicitly at startup.

## Limitations and next steps

- Database calls inside the async loop are blocking. This is fine at small scale, but a larger system would use an async driver or a separate worker process.
- The worker runs inside the API process, so running several API replicas would run duplicate checks.
- No authentication yet.
- Next: a web dashboard and Kubernetes deployment.
