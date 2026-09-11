"""Trend Engine: pluggable providers for Spotify, YouTube, Billboard, TikTok."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx
from bs4 import BeautifulSoup

from app.core.plugins import registry


@dataclass
class Trend:
    source: str
    title: str
    artist: str = ""
    rank: int = 0
    score: float = 0.0
    genre: str = ""
    url: str = ""


class TrendProvider(Protocol):
    name: str
    def fetch(self, limit: int = 20) -> list[Trend]: ...


# ---- Spotify (Client Credentials flow; falls back to empty on missing creds) ----
class SpotifyProvider:
    name = "spotify"

    def __init__(self, client_id: str = "", client_secret: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret

    def fetch(self, limit: int = 20) -> list[Trend]:
        if not self.client_id or not self.client_secret:
            return []
        try:
            token = httpx.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                timeout=15,
            ).json().get("access_token")
            if not token:
                return []
            # Global Top 50 playlist as proxy for charts
            r = httpx.get(
                "https://api.spotify.com/v1/playlists/37i9dQZEVXbMDoHDwVN2tF/tracks?limit=" + str(limit),
                headers={"Authorization": f"Bearer {token}"}, timeout=15,
            ).json()
            out = []
            for i, item in enumerate(r.get("items", []), 1):
                t = (item or {}).get("track") or {}
                artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
                out.append(Trend(source="spotify", title=t.get("name", "Unknown"),
                                 artist=artists, rank=i, score=float(limit - i + 1),
                                 url=(t.get("external_urls") or {}).get("spotify", "")))
            return out
        except Exception:
            return []


# ---- YouTube Music trends (Data API v3 mostPopular music; fallback empty) ----
class YouTubeProvider:
    name = "youtube"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def fetch(self, limit: int = 20) -> list[Trend]:
        if not self.api_key:
            return []
        try:
            r = httpx.get("https://www.googleapis.com/youtube/v3/videos", params={
                "part": "snippet", "chart": "mostPopular", "maxResults": limit,
                "regionCode": "US", "videoCategoryId": "10", "key": self.api_key,
            }, timeout=15).json()
            out = []
            for i, item in enumerate(r.get("items", []), 1):
                sn = item.get("snippet", {})
                out.append(Trend(source="youtube", title=sn.get("title", "Unknown"),
                                 artist=sn.get("channelTitle", ""), rank=i,
                                 score=float(limit - i + 1),
                                 url=f"https://youtu.be/{item.get('id')}"))
            return out
        except Exception:
            return []


# ---- Billboard Hot 100 (public page scrape) ----
class BillboardProvider:
    name = "billboard"

    def fetch(self, limit: int = 20) -> list[Trend]:
        try:
            html = httpx.get("https://www.billboard.com/charts/hot-100/",
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=20).text
            soup = BeautifulSoup(html, "html.parser")
            # Billboard markup changes often; best-effort parse of h3 titles
            titles = [h.get_text(strip=True) for h in soup.select("h3")][:limit]
            return [Trend(source="billboard", title=t or f"Track {i}", rank=i,
                          score=float(limit - i + 1))
                    for i, t in enumerate(titles, 1) if t]
        except Exception:
            return []


# ---- TikTok viral sounds (no official public API; pluggable stub) ----
class TikTokProvider:
    name = "tiktok"

    def __init__(self, session_id: str = ""):
        self.session_id = session_id

    def fetch(self, limit: int = 20) -> list[Trend]:
        # Official TikTok Research API requires approval; this stub returns []
        # unless a plugin overrides it. Keeps architecture production-ready
        # without fake data.
        return []


def _register_defaults() -> None:
    from app.core.config import get_settings
    s = get_settings()
    registry.register_trend_provider("spotify", SpotifyProvider(s.spotify_client_id, s.spotify_client_secret))
    registry.register_trend_provider("youtube", YouTubeProvider(s.youtube_api_key))
    registry.register_trend_provider("billboard", BillboardProvider())
    registry.register_trend_provider("tiktok", TikTokProvider(s.tiktok_session_id))


_register_defaults()


def fetch_all_trends(limit_per_source: int = 20) -> list[Trend]:
    trends: list[Trend] = []
    for provider in registry.trend_providers.values():
        try:
            trends.extend(provider.fetch(limit_per_source))
        except Exception:
            continue
    # Normalize: higher score first
    trends.sort(key=lambda t: t.score, reverse=True)
    return trends


def persist_trends(db, trends: list[Trend]):
    from app.models.models import TrendItem
    rows = [TrendItem(source=t.source, title=t.title, artist=t.artist, rank=t.rank,
                      score=t.score, genre=t.genre, url=t.url) for t in trends]
    db.add_all(rows)
    db.commit()
    return rows
