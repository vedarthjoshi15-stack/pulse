import logging
import os

import httpx

logger = logging.getLogger("pulse.alerts")


def build_message(event: str, name: str, url: str, detail: str | None = None) -> str:
    if event == "opened":
        suffix = f" ({detail})" if detail else ""
        return f"🔴 **{name}** is DOWN: {url}{suffix}"
    return f"🟢 **{name}** is back UP: {url}"


async def send_alert(
    client: httpx.AsyncClient, event: str, name: str, url: str, detail: str | None = None
) -> bool:
    """Post a message to the Discord webhook. Returns True if it was sent.

    Does nothing (returns False) when DISCORD_WEBHOOK_URL is not set.
    Never raises: a broken alert must not stop the checker.
    """
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        return False
    try:
        resp = await client.post(
            webhook, json={"content": build_message(event, name, url, detail)}, timeout=10.0
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        # log only the error type: the exception text can contain the secret URL
        logger.warning("alert failed: %s", type(exc).__name__)
        return False
