"""SEOService: titles, descriptions, tags, hashtags, keywords + seo_score."""
from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "have", "has",
    "are", "was", "were", "will", "what", "when", "your", "our",
}

TITLE_TEMPLATES = [
    "{topic} — What You Missed",
    "{topic}: Full Breakdown",
    "{topic} Explained in {n} Minutes",
    "Why {topic} Changes Everything",
    "{topic} | Latest Update",
]


def extract_keywords(topic: str, body: str = "", limit: int = 10) -> list[str]:
    counts: dict[str, int] = {}
    for token in _WORD_RE.findall(f"{topic} {body}".lower()):
        if len(token) > 2 and token not in _STOPWORDS:
            counts[token] = counts.get(token, 0) + 1
    topic_tokens = set(_WORD_RE.findall(topic.lower()))
    return sorted(counts, key=lambda t: (t in topic_tokens, counts[t]), reverse=True)[:limit]


def generate_hashtags(keywords: list[str], limit: int = 8) -> list[str]:
    tags = ["#football"]
    for kw in keywords:
        tag = "#" + re.sub(r"[^a-z0-9]", "", kw.lower())
        if tag not in tags and len(tag) > 2:
            tags.append(tag)
        if len(tags) >= limit:
            break
    return tags


def generate_titles(topic: str, keywords: list[str], count: int = 5) -> list[str]:
    titles = []
    for i, template in enumerate(TITLE_TEMPLATES[:count]):
        titles.append(template.format(topic=topic, n=(i % 9) + 2))
    # Keyword-led variant for search coverage.
    if keywords:
        titles.append(f"{' '.join(k.title() for k in keywords[:3])} — {topic}")
    return titles[:count]


def generate_description(topic: str, summary: str, keywords: list[str], hashtags: list[str]) -> str:
    lines = [
        f"{topic} — full breakdown and analysis.",
        "",
        summary.strip() or f"Everything you need to know about {topic}.",
        "",
        "Keywords: " + ", ".join(keywords[:8]),
        "",
        " ".join(hashtags[:5]),
        "",
        "Subscribe for daily football intelligence. #footballpulse",
    ]
    return "\n".join(lines)


def score_seo(titles: list[str], description: str, keywords: list[str], hashtags: list[str]) -> float:
    """0..1: title length 30–70 chars, keyword in title, description ≥100 chars,
    3–8 hashtags, ≥5 keywords."""
    best_title = max(titles, key=len) if titles else ""
    parts = [
        1.0 if 30 <= len(best_title) <= 70 else 0.5,
        1.0 if keywords and any(k.lower() in best_title.lower() for k in keywords[:5]) else 0.3,
        1.0 if len(description) >= 100 else 0.5,
        1.0 if 3 <= len(hashtags) <= 8 else 0.5,
        1.0 if len(keywords) >= 5 else 0.5,
    ]
    return round(sum(parts) / len(parts), 3)


def generate_seo(topic: str, summary: str = "", body: str = "") -> dict:
    keywords = extract_keywords(topic, body)
    hashtags = generate_hashtags(keywords)
    titles = generate_titles(topic, keywords)
    description = generate_description(topic, summary, keywords, hashtags)
    return {
        "title_options": titles,
        "description": description,
        "keywords": keywords,
        "hashtags": hashtags,
        "seo_score": score_seo(titles, description, keywords, hashtags),
    }
