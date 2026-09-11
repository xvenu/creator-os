"""Plugin architecture: simple entrypoint-style registry.

A plugin is any object with `name` and `register(registry)` or a module
exposing `register_plugin(manager)`. Third-party plugins live in ./plugins/.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PluginRegistry:
    trend_providers: dict[str, Any] = field(default_factory=dict)
    publishers: dict[str, Any] = field(default_factory=dict)
    content_generators: dict[str, Any] = field(default_factory=dict)
    hooks: dict[str, list[Callable]] = field(default_factory=dict)

    def register_trend_provider(self, name: str, provider: Any) -> None:
        self.trend_providers[name] = provider

    def register_publisher(self, name: str, publisher: Any) -> None:
        self.publishers[name] = publisher

    def register_content_generator(self, name: str, generator: Any) -> None:
        self.content_generators[name] = generator

    def on(self, event: str, fn: Callable) -> None:
        self.hooks.setdefault(event, []).append(fn)

    def emit(self, event: str, *args, **kwargs) -> list[Any]:
        return [fn(*args, **kwargs) for fn in self.hooks.get(event, [])]


registry = PluginRegistry()


def load_plugins(package: str = "plugins") -> PluginRegistry:
    """Import all submodules of `plugins/` so they self-register."""
    try:
        pkg = importlib.import_module(package)
    except ImportError:
        return registry
    for mod in pkgutil.iter_modules(pkg.__path__):
        try:
            importlib.import_module(f"{package}.{mod.name}")
        except Exception:
            continue
    return registry
