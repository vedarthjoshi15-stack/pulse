import asyncio

import httpx

from app.services.alerts import build_message, send_alert


def _send(handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await send_alert(client, "opened", "Dead", "https://example.com", "ConnectError")

    return asyncio.run(go())


def test_build_message_down():
    msg = build_message("opened", "Dead", "https://example.com", "ConnectError")
    assert "DOWN" in msg and "Dead" in msg and "ConnectError" in msg


def test_build_message_up():
    assert "UP" in build_message("resolved", "Dead", "https://example.com")


def test_no_webhook_means_no_alert(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    assert _send(lambda req: httpx.Response(204)) is False


def test_alert_is_posted_to_webhook(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/hook")
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(204)

    assert _send(handler) is True
    assert len(seen) == 1
    assert b"DOWN" in seen[0].content


def test_failed_alert_does_not_raise(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.test/hook")
    assert _send(lambda req: httpx.Response(500)) is False
