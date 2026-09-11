"""Global agent registry."""
from __future__ import annotations

from app.agents.base import BaseAgent
from app.core.logging import get_logger

log = get_logger("agents.registry")


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"Agent already registered: {agent.name}")
        self._agents[agent.name] = agent
        log.info("agent_registered", agent=agent.name)

    def get(self, name: str) -> BaseAgent:
        try:
            return self._agents[name]
        except KeyError:
            raise KeyError(f"Unknown agent: {name}") from None

    def list(self) -> list[dict]:
        return [
            {"name": a.name, "description": a.metadata.description, "version": a.metadata.version}
            for a in self._agents.values()
        ]

    def names(self) -> list[str]:
        return sorted(self._agents.keys())


registry = AgentRegistry()
