"""
Logistics orchestrator — ASI:One Chat Protocol + swarm handlers.

Implementation lives in `protocols/chat.py` (single source of truth).
"""
import shared.env_loader  # noqa: F401

from agents.orchestrator.protocols.chat import orchestrator_agent

__all__ = ["orchestrator_agent"]

if __name__ == "__main__":
    orchestrator_agent.run()
