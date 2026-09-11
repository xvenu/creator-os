"""Bridge: import Creator-OS shared layer from inside music-pulse.

Resolves the creator-os root (parent of the pulse dir) and exposes the
shared event bus / knowledge / network orchestrator. Spec paths
`creator_os/shared/*` map to `<creator-os-root>/shared/*`.
"""
import os
import sys

_PULSE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CREATOR_ROOT = os.path.dirname(_PULSE_ROOT)
if _CREATOR_ROOT not in sys.path:
    sys.path.insert(0, _CREATOR_ROOT)

from shared import event_bus, knowledge, notifications  # noqa: E402
from shared import orchestrator as network_orchestrator  # noqa: E402
from shared import contracts, telegram as telegram_agent  # noqa: E402

__all__ = ["event_bus", "knowledge", "network_orchestrator",
           "notifications", "contracts", "telegram_agent"]
