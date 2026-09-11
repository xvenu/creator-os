"""Pulse Telegram bot — DEPRECATED.

Ownership moved to Creator-OS (shared/telegram/: Creator-OS Telegram Agent).
This module is retained for backward compatibility only: all commands keep
working, but the Pulse operates fully without Telegram (bot is opt-in,
separate process, never on the publishing/decision/recovery path).
New deployments should run the Creator-OS agent instead.
"""
from __future__ import annotations
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.core.config import get_settings
from app.core.database import SessionLocal, init_db

log = logging.getLogger("bot")


def _guard(update: Update) -> bool:
    settings = get_settings()
    if not settings.admin_ids:
        return True  # open if unconfigured (dev); restrict in prod via env
    uid = update.effective_user.id if update.effective_user else 0
    return uid in settings.admin_ids


async def _reply(update: Update, text: str) -> None:
    if update.message:
        await update.message.reply_text(text[:4000])


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _guard(update):
        return
    await _reply(update, "🎵 MusicPulse ready.\n/trends /generate <kind> <topic> /stats /recommend /audit")


async def trends(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _guard(update):
        return
    init_db()
    db = SessionLocal()
    try:
        from app.modules.trends.engine import fetch_all_trends, persist_trends
        ts = fetch_all_trends(5)
        persist_trends(db, ts)
        lines = [f"{t.source}: {t.title} — {t.artist}" for t in ts[:10]] or ["No trends (API keys missing?)"]
        await _reply(update, "\n".join(lines))
    finally:
        db.close()


async def generate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _guard(update):
        return
    if len(ctx.args) < 2:
        await _reply(update, "Usage: /generate <news|profile|review|ranking|short> <topic>")
        return
    kind, topic = ctx.args[0], " ".join(ctx.args[1:])
    db = SessionLocal()
    try:
        from app.modules.content.engine import generate_content, persist_content
        c = generate_content(kind, topic)
        row = persist_content(db, c)
        await _reply(update, f"✅ #{row.id} {row.title}\n{row.body[:1000]}")
    except Exception as exc:
        await _reply(update, f"Error: {exc}")
    finally:
        db.close()


async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _guard(update):
        return
    db = SessionLocal()
    try:
        from app.modules.analytics.engine import totals, engagement_rate
        t = totals(db)
        await _reply(update, f"Views {t['views']} | Eng {t['engagement']} | "
                             f"Followers Δ {t['followers_delta']} | Rate {engagement_rate(db)}")
    finally:
        db.close()


async def recommend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _guard(update):
        return
    db = SessionLocal()
    try:
        from app.modules.learning.engine import recommend as rec
        rs = rec(db, 5)
        await _reply(update, "\n".join(
            f"• {r['genre']}/{r['format']}: {r['suggested_topic']}" for r in rs) or "No data yet")
    finally:
        db.close()


def _admin_only(func):
    """Decorator: admin-protected Phase 2 commands."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        from app.core.config import get_settings as _gs
        s = _gs()
        uid = update.effective_user.id if update.effective_user else 0
        if s.admin_ids and uid not in s.admin_ids:
            if update.message:
                await update.message.reply_text("⛔ Admin only.")
            return
        await func(update, ctx)
    return wrapper


@_admin_only
async def markets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.market_intelligence.engine import fastest_growing, trend_migration
    db = SessionLocal()
    try:
        fast = fastest_growing(db, "artist", limit=5)
        mig = trend_migration(db)[:5]
        lines = ["🌍 Fastest artists:"] + [f"• {a['key']} ({a['velocity']})" for a in fast]
        lines += ["🌐 Cross-border:"] + [f"• {m['title']} — {m['artist']} [{m['countries']}]" for m in mig]
        await _reply(update, "\n".join(lines) or "No market data yet")
    finally:
        db.close()


@_admin_only
async def profitability(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.profitability.engine import leaderboard
    db = SessionLocal()
    try:
        rows = leaderboard(db, limit=5)
        await _reply(update, "💰 Top genres:\n" + "\n".join(
            f"• {r['genre']}: {r['score']}" for r in rows) or "No data yet")
    finally:
        db.close()


@_admin_only
async def discover(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.discovery.engine import weekly_breakout_predictions
    db = SessionLocal()
    try:
        rows = weekly_breakout_predictions(db, 5)
        await _reply(update, "🚀 Breakout predictions:\n" + "\n".join(
            f"• {r['artist']} ({r['confidence']})" for r in rows) or "No data yet")
    finally:
        db.close()


@_admin_only
async def revenue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.revenue.engine import summary
    db = SessionLocal()
    try:
        s = summary(db)
        await _reply(update, f"📊 Total ${s['total']} | MRR ${s['mrr']['mrr_30d']} "
                             f"({s['mrr']['progress'] * 100:.1f}% of target)")
    finally:
        db.close()


@_admin_only
async def sponsors(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.sponsorships.engine import campaign_performance
    db = SessionLocal()
    try:
        rows = campaign_performance(db, 5)
        await _reply(update, "🤝 Campaigns:\n" + "\n".join(
            f"• {r['name']}: ROI {r['roi']}" for r in rows) or "No campaigns yet")
    finally:
        db.close()


@_admin_only
async def competitors(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.competitors.engine import content_gaps
    db = SessionLocal()
    try:
        rows = content_gaps(db, limit=5)
        await _reply(update, "🕵️ Content gaps:\n" + "\n".join(
            f"• {r['topic']} ({r['competitor_mentions']}×)" for r in rows) or "No data yet")
    finally:
        db.close()


@_admin_only
async def executive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.executive.engine import ExecutiveAgent
    db = SessionLocal()
    try:
        out = ExecutiveAgent.run(db)
        await _reply(update, f"🏛️ Exec pass: strategy #{out['strategy']['id']} "
                             f"({out['strategy']['horizon']}), {out['scored']} scored, "
                             f"focus {out['focus']['genre']['chosen']}/"
                             f"{out['focus']['market']['chosen']}")
    finally:
        db.close()


@_admin_only
async def strategy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.executive.engine import generate_strategy
    horizon = (ctx.args[0] if ctx.args else "daily")
    db = SessionLocal()
    try:
        s = generate_strategy(db, horizon)
        await _reply(update, f"🗺️ {horizon} strategy: {', '.join(s['genres'])} | "
                             f"{s['posting_volume']} posts | ${s['revenue_target']}")
    except Exception as exc:
        await _reply(update, f"Error: {exc}")
    finally:
        db.close()


@_admin_only
async def memory(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.memory.engine import lessons
    db = SessionLocal()
    try:
        rows = lessons(db, 5)
        await _reply(update, "🧠 Lessons:\n" + "\n".join(
            f"• [{r['kind']}] {r['title']}" for r in rows) or "Memory empty")
    finally:
        db.close()


@_admin_only
async def opportunities(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.allocation.engine import priority_queue
    db = SessionLocal()
    try:
        rows = priority_queue(db, 5)
        await _reply(update, "💡 Top opportunities:\n" + "\n".join(
            f"• {r['key']} ({r['impact']})" for r in rows) or "No data yet")
    finally:
        db.close()


@_admin_only
async def decisions_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.decision.engine import decisions
    db = SessionLocal()
    try:
        rows = decisions(db, 5)
        await _reply(update, "📜 Decisions:\n" + "\n".join(
            f"• {r['chosen']}: {r['question'][:60]}" for r in rows) or "No decisions yet")
    finally:
        db.close()


@_admin_only
async def autonomy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.autonomy.engine import run_cycle, is_running
    db = SessionLocal()
    try:
        if not is_running():
            await _reply(update, "⏸️ Autonomy stopped. Use /api override to resume.")
            return
        out = run_cycle(db)
        await _reply(update, f"⚙️ Cycle #{out.get('cycle_id')}: {out.get('status')}")
    finally:
        db.close()


@_admin_only
async def warroom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.warroom.engine import attack_strategies
    db = SessionLocal()
    try:
        rows = attack_strategies(db, 3)
        await _reply(update, "⚔️ Attack plans:\n" + "\n".join(
            f"• {r['target']}: {r['play'][:80]}" for r in rows) or "No data yet")
    finally:
        db.close()


@_admin_only
async def growth(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.acquisition.engine import growth_report
    db = SessionLocal()
    try:
        r = growth_report(db)
        await _reply(update, f"📈 +{r['followers_per_day']}/day followers | "
                             f"conv {r['funnel']['conversion_rate']} | CPA ${r['funnel']['cpa']}")
    finally:
        db.close()


@_admin_only
async def predict(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.prediction.engine import forecast_report
    db = SessionLocal()
    try:
        rows = forecast_report(db, 30, 5)
        await _reply(update, "🔮 Top forecasts:\n" + "\n".join(
            f"• {r['subject']} ({r['confidence']})" for r in rows) or "No forecasts yet")
    finally:
        db.close()


@_admin_only
async def breakouts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.breakout.engine import watchlist
    db = SessionLocal()
    try:
        rows = watchlist(db, limit=5)
        await _reply(update, "🚨 Breakouts:\n" + "\n".join(
            f"• {r['subject']} ({r['signal']})" for r in rows) or "No alerts")
    finally:
        db.close()


@_admin_only
async def assets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.assets.engine import valuation_report
    db = SessionLocal()
    try:
        v = valuation_report(db)
        await _reply(update, f"🏠 Portfolio value: ${v['total_valuation']} "
                             f"across {len(v['assets'])} assets")
    finally:
        db.close()


@_admin_only
async def network(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.network.engine import nodes
    db = SessionLocal()
    try:
        ns = nodes(db)
        await _reply(update, "🌐 Network:\n" + "\n".join(
            f"• {n['name']} ({n['kind']})" for n in ns[:10]) or "No nodes yet")
    finally:
        db.close()


@_admin_only
async def monetize(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.monetization.engine import InventoryManager
    db = SessionLocal()
    try:
        inv = InventoryManager.utilization(db)
        await _reply(update, "💼 Open inventory:\n" + "\n".join(
            f"• {k}: {v}" for k, v in inv["available"].items()))
    finally:
        db.close()


@_admin_only
async def forecast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.forecasting.engine import generate
    scope = (ctx.args[0] if ctx.args else "revenue")
    db = SessionLocal()
    try:
        f = generate(db, scope, "monthly")
        await _reply(update, f"📊 {scope} monthly: {f['projection'][:4]} | "
                             f"risks: {', '.join(f['risks'])}")
    except Exception as exc:
        await _reply(update, f"Error: {exc}")
    finally:
        db.close()


@_admin_only
async def products(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.products.engine import totals
    db = SessionLocal()
    try:
        t = totals(db)
        await _reply(update, f"🛍️ {t['sales']} sales, ${t['revenue']} revenue")
    finally:
        db.close()


@_admin_only
async def zoza(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.zoza.engine import ZozaConnector, render_report
    db = SessionLocal()
    try:
        ping = ZozaConnector.ping()
        jobs = render_report(db)[:5]
        lines = [f"🎬 Zoza Video Factory: {'online' if ping['reachable'] else 'offline'}"]
        lines += [f"• #{j['job_id']} {j['state']}" for j in jobs]
        await _reply(update, "\n".join(lines))
    finally:
        db.close()


@_admin_only
async def packages(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.content_gateway.engine import list_packages
    db = SessionLocal()
    try:
        rows = list_packages(db, limit=5)
        await _reply(update, "📦 Packages:\n" + "\n".join(
            f"• [{r['type']}] {r['title'][:60]} ({r['priority']})" for r in rows) or "Queue empty")
    finally:
        db.close()


@_admin_only
async def videos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.video_intelligence.engine import best_formats
    db = SessionLocal()
    try:
        rows = best_formats(db, 5)
        await _reply(update, "📊 Best video formats:\n" + "\n".join(
            f"• {r['format']}: {r['score']}" for r in rows) or "No video data yet")
    finally:
        db.close()


@_admin_only
async def pipeline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.zoza.engine import run_pipeline
    db = SessionLocal()
    try:
        out = run_pipeline(db, limit=3, actor="telegram")
        await _reply(update, f"🔁 Pipeline: {out.get('status')} "
                             f"({out.get('stages', {}).get('dispatched', '?')})")
    finally:
        db.close()


@_admin_only
async def events(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        from app.core.shared import event_bus
        rows = event_bus.history(8)
        await _reply(update, "📡 Bus:\n" + "\n".join(
            f"• {e['event_type']} ← {e['source_pulse']}" for e in rows) or "Bus empty")
    except Exception as exc:
        await _reply(update, f"Error: {exc}")


@_admin_only
async def network_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        from app.core.shared import network_orchestrator as orch
        orch.heartbeat("music-pulse", "healthy")
        rep = orch.network_report()
        await _reply(update, f"🌐 {rep['healthy']} healthy pulses, "
                             f"queue {rep['total_queue']}, load {rep['network_load']}")
    except Exception as exc:
        await _reply(update, f"Error: {exc}")


@_admin_only
async def knowledge_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        from app.core.shared import knowledge
        q = " ".join(ctx.args) if ctx.args else ""
        rows = knowledge.search("artist", q, limit=5)
        await _reply(update, "🧠 Knowledge:\n" + "\n".join(
            f"• {r['key']}" for r in rows) or "Nothing stored yet")
    except Exception as exc:
        await _reply(update, f"Error: {exc}")


@_admin_only
async def feedback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.feedback.engine import apply_feedback
    db = SessionLocal()
    try:
        out = apply_feedback(db, actor="telegram")
        await _reply(update, f"🔄 Feedback applied: {out['events']} events, "
                             f"${out['revenue_attributed']} attributed")
    finally:
        db.close()


@_admin_only
async def reality(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.reality.engine import RealityEngine
    topic = " ".join(ctx.args) if ctx.args else "daily charts"
    db = SessionLocal()
    try:
        rep = RealityEngine.report(db, topic)
        await _reply(update, f"📰 Reality: {topic}\n"
                             f"verdict: {rep['verification']['verdict']} | "
                             f"sources: {len(rep['sources'])}")
    finally:
        db.close()


@_admin_only
async def sources(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.source_intelligence.engine import recommend_sources
    db = SessionLocal()
    try:
        rows = recommend_sources(db, limit=5)
        await _reply(update, "📚 Top sources:\n" + "\n".join(
            f"• {r['name']} ({r['trust']})" for r in rows) or "No sources yet")
    finally:
        db.close()


@_admin_only
async def assets_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.media_acquisition.engine import asset_report
    db = SessionLocal()
    try:
        rows = asset_report(db, limit=5)
        await _reply(update, "🖼️ Assets:\n" + "\n".join(
            f"• {r['title'][:50]} [{r['rights']}]" for r in rows) or "No assets yet")
    finally:
        db.close()


@_admin_only
async def verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.verification.engine import verify_claim
    subject = " ".join(ctx.args) if ctx.args else ""
    if not subject:
        await _reply(update, "Usage: /verify <claim>")
        return
    db = SessionLocal()
    try:
        out = verify_claim(db, subject, "claim", actor="telegram")
        await _reply(update, f"Verdict: {out['verdict']} — {out['rationale']}")
    finally:
        db.close()


@_admin_only
async def artists(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.artist_intelligence.engine import top_artists
    db = SessionLocal()
    try:
        rows = top_artists(db, 5)
        await _reply(update, "🎤 Top artists:\n" + "\n".join(
            f"• {r['artist']} ({r['momentum']})" for r in rows) or "No intel yet")
    finally:
        db.close()


@_admin_only
async def labels(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.label_intelligence.engine import active_labels
    db = SessionLocal()
    try:
        rows = active_labels(db, 5)
        await _reply(update, "🏷️ Active labels:\n" + "\n".join(
            f"• {r['label']} ({r['activity']})" for r in rows) or "No intel yet")
    finally:
        db.close()


@_admin_only
async def newsroom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.newsroom.engine import reports
    db = SessionLocal()
    try:
        rows = reports(db, limit=5)
        await _reply(update, "🗞️ Latest:\n" + "\n".join(
            f"• [{r['verification']}] {r['title'][:60]}" for r in rows) or "No reports yet")
    finally:
        db.close()


@_admin_only
async def documentary(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.modules.documentary.engine import build_project
    subject = " ".join(ctx.args) if ctx.args else ""
    if not subject:
        await _reply(update, "Usage: /documentary <artist>")
        return
    db = SessionLocal()
    try:
        proj = build_project(db, subject, actor="telegram")
        await _reply(update, f"🎬 Project #{proj['id']}: {proj['brief'][:200]}")
    finally:
        db.close()


def build_app() -> Application:
    import warnings
    warnings.warn("music-pulse bot is deprecated; use Creator-OS Telegram agent",
                  DeprecationWarning, stacklevel=2)
    token = get_settings().telegram_bot_token
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trends", trends))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("recommend", recommend))
    app.add_handler(CommandHandler("markets", markets))
    app.add_handler(CommandHandler("profitability", profitability))
    app.add_handler(CommandHandler("discover", discover))
    app.add_handler(CommandHandler("revenue", revenue))
    app.add_handler(CommandHandler("sponsors", sponsors))
    app.add_handler(CommandHandler("competitors", competitors))
    app.add_handler(CommandHandler("executive", executive))
    app.add_handler(CommandHandler("strategy", strategy))
    app.add_handler(CommandHandler("memory", memory))
    app.add_handler(CommandHandler("opportunities", opportunities))
    app.add_handler(CommandHandler("decisions", decisions_cmd))
    app.add_handler(CommandHandler("autonomy", autonomy))
    app.add_handler(CommandHandler("warroom", warroom))
    app.add_handler(CommandHandler("growth", growth))
    app.add_handler(CommandHandler("predict", predict))
    app.add_handler(CommandHandler("breakouts", breakouts))
    app.add_handler(CommandHandler("assets", assets))
    app.add_handler(CommandHandler("network", network))
    app.add_handler(CommandHandler("monetize", monetize))
    app.add_handler(CommandHandler("forecast", forecast))
    app.add_handler(CommandHandler("products", products))
    app.add_handler(CommandHandler("zoza", zoza))
    app.add_handler(CommandHandler("packages", packages))
    app.add_handler(CommandHandler("videos", videos))
    app.add_handler(CommandHandler("pipeline", pipeline))
    app.add_handler(CommandHandler("events", events))
    app.add_handler(CommandHandler("network", network_cmd))
    app.add_handler(CommandHandler("knowledge", knowledge_cmd))
    app.add_handler(CommandHandler("feedback", feedback))
    app.add_handler(CommandHandler("reality", reality))
    app.add_handler(CommandHandler("sources", sources))
    app.add_handler(CommandHandler("assets", assets_cmd))
    app.add_handler(CommandHandler("verify", verify))
    app.add_handler(CommandHandler("artists", artists))
    app.add_handler(CommandHandler("labels", labels))
    app.add_handler(CommandHandler("newsroom", newsroom))
    app.add_handler(CommandHandler("documentary", documentary))
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    build_app().run_polling()
