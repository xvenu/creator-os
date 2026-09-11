"""Creator-OS Telegram Agent — the ONLY Telegram owner in the network.

Pulse bots (e.g. music-pulse/app/bot) are deprecated shims. This agent:
receives system/pulse/factory alerts and answers /health /pulses /revenue
/alerts /events /network. Run: python -m shared.telegram (from creator-os/).
"""
from __future__ import annotations
import logging
import os

log = logging.getLogger("creator-telegram")

COMMANDS = ("health", "pulses", "revenue", "alerts", "events", "network")


def summaries() -> dict:
    """Aggregate cross-pulse state for answers. Fail-open per source."""
    out: dict = {}
    try:
        from shared import orchestrator as orch
        out["network"] = orch.network_report()
        out["registered"] = orch.list_registered()
    except Exception as exc:
        out["network_error"] = str(exc)
    try:
        from shared import event_bus
        out["events"] = event_bus.history(5)
    except Exception as exc:
        out["events_error"] = str(exc)
    try:
        from shared import notifications
        out["alerts"] = notifications.recent(5)
    except Exception as exc:
        out["alerts_error"] = str(exc)
    return out


def answer(command: str) -> str:
    """Pure logic behind each command (testable without Telegram)."""
    if command not in COMMANDS:
        raise ValueError(f"unknown command: {command}")
    s = summaries()
    net = s.get("network", {})
    if command == "health":
        return (f"Creator-OS OK | pulses healthy: {net.get('healthy', '?')} | "
                f"queue {net.get('total_queue', '?')}")
    if command == "pulses":
        reg = s.get("registered", [])
        return "Pulses:\n" + "\n".join(
            f"• {r['name']} ({r['kind']})" for r in reg) if reg else "No pulses registered"
    if command == "revenue":
        alerts = [a for a in s.get("alerts", []) if a["event"] == "revenue"][:5]
        return "Revenue alerts:\n" + "\n".join(
            f"• {a['message'][:100]}" for a in alerts) if alerts else "No revenue alerts"
    if command == "alerts":
        alerts = s.get("alerts", [])[:5]
        return "Alerts:\n" + "\n".join(
            f"• [{a['event']}] {a['message'][:100]}" for a in alerts) if alerts else "No alerts"
    if command == "events":
        evs = s.get("events", [])[:5]
        return "Events:\n" + "\n".join(
            f"• {e['event_type']} ← {e['source_pulse']}" for e in evs) if evs else "Bus empty"
    if command == "network":
        pulses = net.get("pulses", [])
        return "Network:\n" + "\n".join(
            f"• {p['pulse']}: {p['state']}" for p in pulses) if pulses else "No heartbeats"
    raise ValueError(command)


def build_app():
    """python-telegram-bot application. Requires CREATOR_TELEGRAM_TOKEN."""
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes

    async def _reply(update: Update, text: str):
        if update.message:
            await update.message.reply_text(text[:4000])

    def _make(name):
        async def _h(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            await _reply(update, answer(name))
        return _h

    token = os.environ.get("CREATOR_TELEGRAM_TOKEN", "")
    app = Application.builder().token(token).build()
    for cmd in COMMANDS:
        app.add_handler(CommandHandler(cmd, _make(cmd)))
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    log.warning("Creator-OS Telegram agent starting (sole Telegram owner)")
    build_app().run_polling()
