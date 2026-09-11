"""NewsService: ingest, deduplicate, cluster, rank football news.

Deterministic, dependency-free logic. All thresholds documented below.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re

# Source reliability weights (0..1). Unknown sources default to 0.4.
SOURCE_RELIABILITY: dict[str, float] = {
    "bbc sport": 0.95,
    "the athletic": 0.95,
    "sky sports": 0.9,
    "reuters": 0.9,
    "associated press": 0.9,
    "espn": 0.85,
    "guardian": 0.85,
    "fabrizio romano": 0.85,
    "david ornstein": 0.95,
    "marca": 0.7,
    "as": 0.65,
    "l'equipe": 0.8,
    "lequipe": 0.8,
    "bild": 0.7,
    "gazzetta": 0.7,
    "goal": 0.6,
    "talksport": 0.55,
    "daily mail": 0.5,
    "the sun": 0.45,
}

BREAKING_KEYWORDS = (
    "breaking", "confirmed", "official", "done deal", "here we go",
    "sacked", "appointed", "injury", "record signing", "deadline day",
)

BIG_CLUBS = (
    "arsenal", "manchester city", "man city", "liverpool", "chelsea",
    "manchester united", "man united", "tottenham", "real madrid",
    "barcelona", "bayern", "psg", "juventus", "inter", "milan",
    "atletico", "dortmund", "newcastle",
)

COMPETITIONS = (
    "premier league", "champions league", "world cup", "euros",
    "la liga", "serie a", "bundesliga", "ligue 1", "fa cup",
    "europa league", "nations league", "copa america",
)

_WORD_RE = re.compile(r"[a-z0-9]+")
_CAP_PAIR_RE = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2})\b")
_STOP_PHRASES = {
    "Premier League", "Champions League", "World Cup", "Europa League",
    "Nations League", "Copa America", "Fa Cup", "La Liga", "Serie A",
}


def content_hash(title: str, url: str) -> str:
    """Stable SHA-256 over normalized title + URL."""
    norm = (title.strip().lower() + "|" + url.strip().lower()).encode("utf-8")
    return hashlib.sha256(norm).hexdigest()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def summarize(body: str | None, title: str, max_chars: int = 280) -> str:
    """First-sentences extractive summary; falls back to title."""
    if not body:
        return title
    sentences = re.split(r"(?<=[.!?])\s+", body.strip())
    out = ""
    for s in sentences:
        candidate = (out + " " + s).strip() if out else s
        if len(candidate) > max_chars:
            break
        out = candidate
    return out or title[:max_chars]


def source_reliability(source: str) -> float:
    key = source.strip().lower()
    for name, weight in SOURCE_RELIABILITY.items():
        if name in key or key in name:
            return weight
    return 0.4


def extract_entities(title: str, body: str | None = None) -> dict:
    """Lexicon-based entity extraction (deterministic, no ML)."""
    text = f"{title} {body or ''}"
    lowered = text.lower()
    clubs = sorted({c for c in BIG_CLUBS if c in lowered})
    competitions = sorted({c for c in COMPETITIONS if c in lowered})
    candidates = _CAP_PAIR_RE.findall(text)
    players = sorted({c for c in candidates if c not in _STOP_PHRASES})
    return {"clubs": clubs, "competitions": competitions, "people": players[:10]}


def importance_score(
    title: str,
    body: str | None,
    source: str,
    entities: dict,
    published_at: dt.datetime | None = None,
) -> float:
    """Weighted 0..1 score: reliability 0.35 + keywords 0.25 + entities 0.25 + recency 0.15."""
    lowered = f"{title} {body or ''}".lower()
    reliability = source_reliability(source) * 0.35
    keyword_hits = sum(1 for kw in BREAKING_KEYWORDS if kw in lowered)
    keyword_part = min(keyword_hits / 2.0, 1.0) * 0.25
    entity_count = len(entities.get("clubs", [])) + len(entities.get("competitions", []))
    entity_part = min(entity_count / 3.0, 1.0) * 0.25
    recency_part = 0.15
    if published_at is not None:
        now = dt.datetime.now(dt.timezone.utc)
        pub = published_at if published_at.tzinfo else published_at.replace(tzinfo=dt.timezone.utc)
        age_hours = max((now - pub).total_seconds() / 3600.0, 0.0)
        recency_part = max(0.0, 0.15 * (1.0 - age_hours / 48.0))
    return round(min(reliability + keyword_part + entity_part + recency_part, 1.0), 3)


def is_breaking(title: str, body: str | None, score: float) -> bool:
    lowered = f"{title} {body or ''}".lower()
    has_keyword = any(kw in lowered for kw in BREAKING_KEYWORDS)
    return bool(has_keyword and score >= 0.5)


def ingest_article(raw: dict) -> dict:
    """Normalize one raw article dict into a NewsIntel object (unp persisted)."""
    title = normalize_text(str(raw.get("title", "")))
    source = normalize_text(str(raw.get("source", "unknown")))
    url = str(raw.get("url", "")).strip()
    body = raw.get("body")
    published_at = raw.get("published_at")
    entities = extract_entities(title, body)
    score = importance_score(title, body, source, entities, published_at)
    return {
        "title": title,
        "summary": summarize(body, title),
        "source": source,
        "url": url,
        "published_at": published_at,
        "importance_score": score,
        "breaking_news": is_breaking(title, body, score),
        "entities": entities,
        "content_hash": content_hash(title, url),
    }


def ingest_news(raw_articles: list[dict]) -> list[dict]:
    return [ingest_article(a) for a in raw_articles if str(a.get("title", "")).strip()]


def deduplicate(
    articles: list[dict], known_hashes: set[str] | None = None
) -> tuple[list[dict], list[dict]]:
    """Split into (unique, duplicates) by content_hash.

    known_hashes: hashes already persisted (DB-backed dedup).
    """
    known = set(known_hashes or set())
    unique: list[dict] = []
    duplicates: list[dict] = []
    seen: set[str] = set()
    for article in articles:
        h = article.get("content_hash") or content_hash(article.get("title", ""), article.get("url", ""))
        article["content_hash"] = h
        if h in seen or h in known:
            duplicates.append(article)
        else:
            seen.add(h)
            known.add(h)
            unique.append(article)
    return unique, duplicates


def _title_tokens(title: str) -> set[str]:
    return {t for t in _WORD_RE.findall(title.lower()) if len(t) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_news(articles: list[dict], threshold: float = 0.35) -> list[dict]:
    """Union-find clustering on title Jaccard similarity.

    Returns cluster dicts with story_key, members, trend/importance rollups.
    """
    n = len(articles)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    token_sets = [_title_tokens(a.get("title", "")) for a in articles]
    for i in range(n):
        for j in range(i + 1, n):
            if jaccard(token_sets[i], token_sets[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    clusters = []
    for members in groups.values():
        core = sorted(set().union(*[token_sets[i] for i in members]))
        story_key = hashlib.sha256(" ".join(core).encode()).hexdigest()[:16]
        member_articles = [articles[i] for i in members]
        sources = {a.get("source", "") for a in member_articles}
        importance = max((a.get("importance_score", 0.0) for a in member_articles), default=0.0)
        breaking = any(a.get("breaking_news", False) for a in member_articles)
        trend = trend_score(len(members), len(sources), importance)
        entities: dict[str, list[str]] = {"clubs": [], "competitions": [], "people": []}
        for a in member_articles:
            for k in entities:
                for e in a.get("entities", {}).get(k, []):
                    if e not in entities[k]:
                        entities[k].append(e)
        clusters.append(
            {
                "story_key": story_key,
                "title": max(member_articles, key=lambda a: a.get("importance_score", 0.0))["title"],
                "article_count": len(members),
                "source_count": len(sources),
                "trend_score": trend,
                "importance_score": importance,
                "is_breaking": breaking,
                "article_hashes": [a.get("content_hash", "") for a in member_articles],
                "entities": entities,
            }
        )
    return sorted(clusters, key=lambda c: (c["trend_score"], c["importance_score"]), reverse=True)


def trend_score(article_count: int, source_count: int, max_importance: float) -> float:
    """0..1 trend signal: multi-article + multi-source + importance."""
    count_part = min(article_count / 5.0, 1.0) * 0.4
    source_part = min(source_count / 3.0, 1.0) * 0.35
    return round(count_part + source_part + max_importance * 0.25, 3)


def rank_news(articles: list[dict], limit: int = 20) -> list[dict]:
    """Breaking first, then importance, then recency."""
    def sort_key(a: dict) -> tuple:
        pub = a.get("published_at")
        ts = pub.timestamp() if isinstance(pub, dt.datetime) else 0.0
        return (bool(a.get("breaking_news", False)), float(a.get("importance_score", 0.0)), ts)

    return sorted(articles, key=sort_key, reverse=True)[:limit]
