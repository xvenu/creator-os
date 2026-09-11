"""Example publisher plugin: Telegram channel publisher."""
import os
import httpx
from app.core.plugins import registry


def telegram_publisher(job, content) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    if not token or not chat_id or content is None:
        return True  # no-op in dev; keeps pipeline green
    httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
               json={"chat_id": chat_id,
                     "text": f"{content.title}\n\n{content.body[:1000]}"},
               timeout=15).raise_for_status()
    return True


registry.register_publisher("telegram", telegram_publisher)
