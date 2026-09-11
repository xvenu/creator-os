"""Content Engine: news, profiles, reviews, rankings, short-form.

Uses open-source HF models when available (transformers, lazy import),
otherwise deterministic template generation so the pipeline works offline
and in CI. Pluggable via registry.content_generators.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.core.plugins import registry


@dataclass
class GeneratedContent:
    kind: str  # news|profile|review|ranking|short
    title: str
    body: str
    genre: str = ""
    format: str = ""


def _template_generate(kind: str, topic: str, genre: str = "", artist: str = "") -> GeneratedContent:
    topic = topic or "Today's top track"
    artist = artist or "Rising Star"
    templates = {
        "news": (f"{topic} climbs global charts",
                 f"MusicPulse News — {topic} by {artist} is surging across Spotify, "
                 f"YouTube and TikTok. Genre: {genre or 'pop'}. Streams are up as fans "
                 f"share the track worldwide. Stay tuned for chart updates."),
        "profile": (f"Artist Spotlight: {artist}",
                    f"{artist} blends {genre or 'pop'} with a fresh global sound. "
                    f"Breakout track: {topic}. What to watch: upcoming releases, "
                    f"tour dates, and collaborations."),
        "review": (f"Review: {topic} by {artist}",
                   f"Verdict 8/10. {topic} pairs a sticky hook with {genre or 'pop'} "
                   f"production. High replay value; short-form ready chorus at 0:45."),
        "ranking": (f"Top 5 {genre or 'Global'} tracks right now",
                    f"1. {topic} — {artist}\n2-5. Based on today's Trend Engine scores. "
                    f"Ranked by cross-platform velocity (Spotify + YouTube + TikTok)."),
        "short": (f"{topic} 🔥",
                  f"{artist} — {topic} ({genre or 'pop'}) is blowing up 🎧 "
                  f"#MusicPulse #NowPlaying #Viral"),
    }
    title, body = templates.get(kind, templates["news"])
    fmt = {"news": "article", "profile": "article", "review": "article",
           "ranking": "listicle", "short": "caption"}.get(kind, "article")
    return GeneratedContent(kind=kind, title=title, body=body, genre=genre, format=fmt)


def _hf_generate(kind: str, prompt: str) -> str | None:
    """Try open-source HF model; return None if unavailable (offline/CI-safe)."""
    try:
        from transformers import pipeline  # lazy, optional dep
        from app.core.config import get_settings
        gen = pipeline("text-generation", model=get_settings().hf_model)
        out = gen(prompt, max_new_tokens=120, do_sample=False)
        return out[0]["generated_text"]
    except Exception:
        return None


def generate_content(kind: str, topic: str, genre: str = "", artist: str = "") -> GeneratedContent:
    if kind not in ("news", "profile", "review", "ranking", "short"):
        raise ValueError(f"unknown content kind: {kind}")
    # Plugin override first
    if kind in registry.content_generators:
        try:
            return registry.content_generators[kind](topic=topic, genre=genre, artist=artist)
        except Exception:
            pass
    base = _template_generate(kind, topic, genre, artist)
    # Optionally enrich with OSS model (non-blocking, best effort)
    enriched = _hf_generate(kind, f"{base.title}\n{base.body}")
    if enriched:
        base.body = enriched[:2000]
    return base


def persist_content(db, content: GeneratedContent, status: str = "draft"):
    from app.models.models import ContentItem
    row = ContentItem(kind=content.kind, title=content.title, body=content.body,
                      genre=content.genre, format=content.format, status=status)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
