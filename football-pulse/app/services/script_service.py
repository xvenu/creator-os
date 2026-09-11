"""ScriptGenerationService: briefs → structured scripts + quality scoring.

Supported formats: match_preview | match_review | transfer_update |
breaking_news | prediction_report | tactical_breakdown | football_story |
mini_documentary.

Supported lengths: 30s | 60s | 3min | 5min | 10min (150 wpm assumption).
"""
from __future__ import annotations

VALID_FORMATS = (
    "match_preview", "match_review", "transfer_update", "breaking_news",
    "prediction_report", "tactical_breakdown", "football_story", "mini_documentary",
)

LENGTHS = {
    "30s": {"words": 75, "seconds": 30},
    "60s": {"words": 150, "seconds": 60},
    "3min": {"words": 450, "seconds": 180},
    "5min": {"words": 750, "seconds": 300},
    "10min": {"words": 1500, "seconds": 600},
}

WORDS_PER_MINUTE = 150
QUALITY_THRESHOLD = 0.70

HOOK_TEMPLATES = {
    "match_preview": "Stop what you're doing — {topic} is the game that decides everything.",
    "match_review": "Nobody saw this coming: {topic}, explained in plain words.",
    "transfer_update": "It's happening — {topic}, and the details are massive.",
    "breaking_news": "Breaking right now: {topic}. Here's what we know.",
    "prediction_report": "The data is clear on {topic} — here's the most likely outcome.",
    "tactical_breakdown": "The tactic behind {topic} that nobody is talking about.",
    "football_story": "This story about {topic} will give you goosebumps.",
    "mini_documentary": "The untold story of {topic} — from the beginning.",
}

OUTRO_TEMPLATES = {
    "match_preview": "Drop your score prediction below, and subscribe for the review.",
    "match_review": "Agree with the ratings? Debate us in the comments.",
    "transfer_update": "Subscribe with notifications — this saga moves fast.",
    "breaking_news": "Stay tuned — updates as this story develops.",
    "prediction_report": "Back the data or trust your gut? Comment your pick.",
    "tactical_breakdown": "Share this with someone who loves tactics.",
    "football_story": "If this moved you, share it with a football fan.",
    "mini_documentary": "Part two drops soon — subscribe so you don't miss it.",
}


def _fit_words(text: str, target: int) -> str:
    """Trim or pad (with supporting sentences) to approximate target length."""
    words = text.split()
    if len(words) <= target:
        return text
    return " ".join(words[:target]).rstrip(",.") + "."


def generate_script(brief: dict, content_format: str, length: str = "60s") -> dict:
    """Build {title, hook, body, outro, estimated_duration} from a brief."""
    if content_format not in VALID_FORMATS:
        raise ValueError(f"Unknown format: {content_format}")
    if length not in LENGTHS:
        raise ValueError(f"Unknown length: {length}")
    topic = brief.get("topic", "football")
    facts = [f["text"] if isinstance(f, dict) else str(f) for f in brief.get("facts", [])]
    points = list(brief.get("supporting_points", []))
    target = LENGTHS[length]["words"]

    hook = HOOK_TEMPLATES[content_format].format(topic=topic)
    # Length-aware depth: longer formats cover more facts and angles.
    depth = {"30s": (1, 0), "60s": (2, 1), "3min": (4, 2), "5min": (6, 3), "10min": (8, 4)}[length]
    body_parts = [f"First, {facts[0]}" if facts else f"Here's the full picture on {topic}."]
    for i, fact in enumerate(facts[1:depth[0]], start=2):
        body_parts.append(f"Point {i}: {fact}.")
    for point in points[:depth[1]]:
        if point not in body_parts:
            body_parts.append(f"Also: {point}")
    body = _fit_words(" ".join(body_parts), target)
    outro = OUTRO_TEMPLATES[content_format]
    total_words = len((hook + " " + body + " " + outro).split())
    return {
        "title": f"{topic} — {content_format.replace('_', ' ').title()}",
        "hook": hook,
        "body": body,
        "outro": outro,
        "estimated_duration": {
            "label": length,
            "seconds": LENGTHS[length]["seconds"],
            "estimated_seconds": round(total_words / WORDS_PER_MINUTE * 60),
            "word_count": total_words,
        },
        "content_format": content_format,
    }


def score_quality(script: dict, brief: dict) -> dict:
    """Content Quality Engine → engagement/clarity/retention/monetization/overall.

    - engagement: hook strength (length 8–25 words, punchy punctuation) + CTA in outro
    - clarity: body sentence structure + fact coverage vs brief
    - retention: open loops/questions + body segmentation
    - monetization: advertiser-safe length + evergreen topic breadth
    """
    hook_words = len(script.get("hook", "").split())
    hook_score = 1.0 if 8 <= hook_words <= 25 else 0.5
    if any(m in script.get("hook", "") for m in ("?", "!", "—")):
        hook_score = min(hook_score + 0.1, 1.0)
    outro = script.get("outro", "").lower()
    cta = 1.0 if any(w in outro for w in ("subscribe", "comment", "share")) else 0.4
    engagement = round(0.6 * hook_score + 0.4 * cta, 3)

    body = script.get("body", "")
    sentences = [s for s in body.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    structure = 1.0 if 2 <= len(sentences) <= 12 else 0.6
    brief_facts = brief.get("facts", [])
    covered = sum(1 for f in brief_facts[:4]
                  if str(f.get("text", "")[:20] if isinstance(f, dict) else str(f)[:20]) in body)
    coverage = covered / max(min(len(brief_facts), 4), 1)
    clarity = round(0.5 * structure + 0.5 * coverage, 3)

    loops = sum(body.lower().count(w) for w in ("?", "but ", "however", "also", "point "))
    retention = round(min(0.5 + loops * 0.1, 1.0), 3)

    seconds = script.get("estimated_duration", {}).get("estimated_seconds", 60)
    length_fit = 1.0 if 25 <= seconds <= 660 else 0.6
    monetization = round(0.7 * length_fit + 0.3 * (1.0 if len(brief.get("entities", {}).get("clubs", [])) <= 3 else 0.7), 3)

    overall = round(0.3 * engagement + 0.25 * clarity + 0.25 * retention + 0.2 * monetization, 3)
    return {
        "engagement_score": engagement,
        "clarity_score": clarity,
        "retention_score": retention,
        "monetization_score": monetization,
        "overall_score": overall,
        "approved": overall >= QUALITY_THRESHOLD,
    }
