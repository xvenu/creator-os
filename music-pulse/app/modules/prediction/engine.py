"""Trend Prediction Engine: explainable, auditable forecasts (7/30/90d)."""
from __future__ import annotations

from app.core.audit import audit

HORIZONS = (7, 30, 90)
SUBJECTS = ("artist", "song", "genre", "market")


class _Base:
    subject_type = ""


class TrendPredictor(_Base):
    subject_type = "song"

    @staticmethod
    def forecast(db, subject: str, horizon_days: int = 7) -> dict:
        from app.models.phase4 import TrendPrediction
        from app.modules.market_intelligence.engine import velocity, fastest_growing
        if horizon_days not in HORIZONS:
            raise ValueError(f"horizon must be {HORIZONS}")
        vel = velocity(db, "US", title=subject)
        fast = {f["key"]: f["velocity"] for f in fastest_growing(db, "song", limit=20)}
        momentum = fast.get(subject, abs(vel))
        decay = {7: 1.0, 30: 0.7, 90: 0.4}[horizon_days]
        score = round(max(momentum, 0) * decay, 2)
        conf = round(min(score / 100, 0.95), 2)
        rationale = (f"velocity={vel}, top-song momentum={momentum}, "
                     f"decay x{decay} over {horizon_days}d from country-trend history")
        row = TrendPrediction(subject_type="song", subject=subject,
                              horizon_days=horizon_days, confidence=conf,
                              opportunity=score, rationale=rationale)
        db.add(row)
        db.commit()
        db.refresh(row)
        audit(db, "predictor", "prediction.made", "prediction", row.id,
              {"subject": subject, "horizon": horizon_days})
        return {"id": row.id, "subject": subject, "horizon_days": horizon_days,
                "confidence": conf, "opportunity": score, "rationale": rationale}


class ArtistPredictor(_Base):
    subject_type = "artist"

    @staticmethod
    def forecast(db, subject: str, horizon_days: int = 30) -> dict:
        from app.models.phase4 import TrendPrediction
        from app.modules.discovery.engine import weekly_breakout_predictions
        if horizon_days not in HORIZONS:
            raise ValueError(f"horizon must be {HORIZONS}")
        preds = {p["artist"]: p for p in weekly_breakout_predictions(db, 20)}
        hit = preds.get(subject, {})
        base = float(hit.get("velocity", 0.1)) * 50
        decay = {7: 1.0, 30: 0.8, 90: 0.5}[horizon_days]
        score = round(base * decay, 2)
        rationale = (f"discovery velocity={hit.get('velocity', 0.1)} "
                     f"classification={hit.get('classification', 'unknown')}")
        row = TrendPrediction(subject_type="artist", subject=subject,
                              horizon_days=horizon_days,
                              confidence=round(min(score / 100, 0.95), 2),
                              opportunity=score, rationale=rationale)
        db.add(row)
        db.commit()
        db.refresh(row)
        audit(db, "predictor", "prediction.made", "prediction", row.id,
              {"subject": subject})
        return {"id": row.id, "subject": subject, "confidence": row.confidence,
                "opportunity": score, "rationale": rationale}


class GenrePredictor(_Base):
    subject_type = "genre"

    @staticmethod
    def forecast(db, subject: str, horizon_days: int = 90) -> dict:
        from app.models.phase4 import TrendPrediction
        from app.modules.profitability.engine import growth_forecast
        if horizon_days not in HORIZONS:
            raise ValueError(f"horizon must be {HORIZONS}")
        fc = growth_forecast(db, subject, weeks=4)
        hist = fc["history"]
        slope = (hist[-1] - hist[0]) / 3 if len(hist) == 4 and hist[0] else 0.0
        scale = {7: 1, 30: 4, 90: 12}[horizon_days]
        score = round(max(hist[-1] + slope * scale, 0) / 100, 2)
        rationale = f"4-week view history={hist}, weekly slope={round(slope, 1)}"
        row = TrendPrediction(subject_type="genre", subject=subject,
                              horizon_days=horizon_days,
                              confidence=round(min(score / 50, 0.95), 2),
                              opportunity=score, rationale=rationale)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id, "subject": subject, "opportunity": score,
                "confidence": row.confidence, "rationale": rationale}


class MarketPredictor(_Base):
    subject_type = "market"

    @staticmethod
    def forecast(db, subject: str, horizon_days: int = 30) -> dict:
        from app.models.phase4 import TrendPrediction
        from app.modules.market_intelligence.engine import country_rankings
        if horizon_days not in HORIZONS:
            raise ValueError(f"horizon must be {HORIZONS}")
        ranks = country_rankings(db, subject.upper(), 10)
        heat = sum(r["score"] for r in ranks)
        rationale = f"{len(ranks)} charting items, aggregate heat={round(heat, 1)}"
        row = TrendPrediction(subject_type="market", subject=subject.upper(),
                              horizon_days=horizon_days,
                              confidence=round(min(heat / 500, 0.95), 2),
                              opportunity=round(heat, 2), rationale=rationale)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id, "subject": subject.upper(), "opportunity": row.opportunity,
                "confidence": row.confidence, "rationale": rationale}


def forecast_report(db, horizon_days: int = 30, limit: int = 10) -> list[dict]:
    from app.models.phase4 import TrendPrediction
    rows = (db.query(TrendPrediction)
            .filter(TrendPrediction.horizon_days == horizon_days)
            .order_by(TrendPrediction.opportunity.desc()).limit(limit).all())
    return [{"subject": r.subject, "type": r.subject_type,
             "confidence": r.confidence, "opportunity": r.opportunity,
             "rationale": r.rationale} for r in rows]
