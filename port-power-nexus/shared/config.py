import shared.env_loader  # noqa: F401 — repo root .env

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentAddresses:
    grid_agent: str
    terminal_agent: str
    truck_status_agent: str
    amazon_truck_agent: str
    fedex_truck_agent: str
    ups_truck_agent: str


@dataclass(frozen=True)
class OrchestratorSettings:
    hello_text: str
    outbound_timeout_seconds: int
    addresses: AgentAddresses


_DEFAULT_TERMINAL = "agent1q2dsyxc0g3482s3cewzss6vf4gakd2r8znask0gpmqrnvm0p5n0fy9gsulk"


def load_orchestrator_settings() -> OrchestratorSettings:
    return OrchestratorSettings(
        hello_text=os.getenv("ORCHESTRATOR_HELLO_TEXT", "Hello from Port-Power Nexus"),
        outbound_timeout_seconds=int(
            os.getenv("ORCHESTRATOR_OUTBOUND_TIMEOUT_SECONDS", "15")
        ),
        addresses=AgentAddresses(
            grid_agent=os.getenv(
                "GRID_AGENT_ADDRESS",
                "agent1qdrkj8c6caq7tdmk04r3277ekaukfg7ztxncx0alpddflgz995k4xun8nut",
            ),
            terminal_agent=os.getenv(
                "TERMINAL_AGENT_ADDRESS",
                _DEFAULT_TERMINAL,
            ),
            # Terminal implements TruckStatusRequest → TruckStatusResponse (see agents/terminal/agent.py).
            truck_status_agent=os.getenv(
                "TRUCK_STATUS_AGENT_ADDRESS",
                _DEFAULT_TERMINAL,
            ),
            amazon_truck_agent=os.getenv(
                "AMAZON_TRUCK_AGENT_ADDRESS",
                "agent1qt64xcals30mgjk0vgjykjen7j6wq0m3mp4ny0k5ymnpkaeadmxtqz3hp36",
            ),
            fedex_truck_agent=os.getenv(
                "FEDEX_TRUCK_AGENT_ADDRESS",
                "agent1q0n4pnt8c25efcfzj3v9fwxp6fqw6lmn0yy279czrsem9hzvftgz7n4nmsq",
            ),
            ups_truck_agent=os.getenv(
                "UPS_TRUCK_AGENT_ADDRESS",
                "agent1qtelk9cdqsacsyz6re8edxugphks6z6cgaynn0q5w87m9h3x0zrqxxyslsx",
            ),
        ),
    )
