"""Voice intelligence: select profile, match tone/pacing/emotion/audience."""
from __future__ import annotations

PROFILES: dict[str, dict] = {
    "documentary": {
        "tone": "warm-authoritative", "pacing_wpm": 130, "emotion": "measured",
        "pitch": "mid-low", "audiences": ["general", "documentary", "music"],
        "keywords": ["documentary", "story", "biography", "burna", "artist", "journey"],
    },
    "breaking-news": {
        "tone": "urgent-clear", "pacing_wpm": 170, "emotion": "alert",
        "pitch": "mid", "audiences": ["general", "news"],
        "keywords": ["breaking", "news", "urgent", "update", "announcement"],
    },
    "sports-analysis": {
        "tone": "energetic-analytical", "pacing_wpm": 160, "emotion": "excited-precise",
        "pitch": "mid-high", "audiences": ["sports", "football", "fans"],
        "keywords": ["tactical", "analysis", "arsenal", "match", "football", "sport", "game"],
    },
    "artist-biography": {
        "tone": "intimate-narrative", "pacing_wpm": 125, "emotion": "reverent",
        "pitch": "mid-low", "audiences": ["music", "fans", "general"],
        "keywords": ["biography", "life", "career", "album", "song", "musician", "singer"],
    },
    "historical-story": {
        "tone": "grave-storytelling", "pacing_wpm": 120, "emotion": "solemn",
        "pitch": "low", "audiences": ["history", "documentary", "general"],
        "keywords": ["history", "historical", "archive", "legacy", "era", "past"],
    },
}


def match(voice_profile: str = "", goal: str = "", style: str = "",
          target_audience: str = "") -> dict:
    """Score profiles by explicit request first, then keyword/audience signals."""
    requested = (voice_profile or "").strip().lower().replace("_", "-")
    if requested in PROFILES:
        prof = PROFILES[requested]
        return {"profile": requested, **_public(prof),
                "reason": "explicit voice_profile requested by pulse"}

    haystack = f"{goal} {style} {target_audience}".lower()
    scored: list[tuple[int, str]] = []
    for name, prof in PROFILES.items():
        score = sum(1 for kw in prof["keywords"] if kw in haystack)
        if any(a in haystack for a in prof["audiences"]):
            score += 1
        scored.append((score, name))
    scored.sort(reverse=True)
    best = scored[0][1] if scored[0][0] > 0 else "documentary"
    prof = PROFILES[best]
    reason = ("matched signals in goal/style/audience" if scored[0][0] > 0
              else "no signal matched; documentary fallback")
    return {"profile": best, **_public(prof), "reason": reason}


def _public(prof: dict) -> dict:
    return {"tone": prof["tone"], "pacing_wpm": prof["pacing_wpm"],
            "emotion": prof["emotion"], "pitch": prof["pitch"],
            "audiences": prof["audiences"]}
