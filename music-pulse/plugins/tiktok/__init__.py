"""Example trend plugin: registers a demo TikTok provider override."""
from app.core.plugins import registry
from app.modules.trends.engine import Trend


class DemoTikTok:
    name = "tiktok"

    def fetch(self, limit: int = 10):
        return [Trend(source="tiktok", title=f"Viral Sound {i}", artist="TikTok",
                      rank=i, score=float(limit - i)) for i in range(1, 4)]


# Uncomment to override default stub:
# registry.register_trend_provider("tiktok", DemoTikTok())
