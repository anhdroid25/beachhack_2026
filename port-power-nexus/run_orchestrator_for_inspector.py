"""
Run **only** the Logistics_Orchestrator (single process).

**Aligns with uAgents 0.24.0 + Fetch.ai mailbox docs:** the orchestrator is built with
``mailbox=True`` and still listens on a **dedicated port** (default **8002**) so Local
Agent Inspector can reach ``http://127.0.0.1:<port>/submit`` during Connect → Mailbox.
**Only the orchestrator** uses mailbox; swarm agents use HTTP submit + **unique ports**
(see ``run_swarm_bureau.py``).

Use a **two-terminal** setup (Inspector does not support multi-agent Bureaus in one process):

  Terminal 1:  python run_swarm_bureau.py          # Bureau :8000 (grid + trucks + terminal)
  Terminal 2:  python run_orchestrator_for_inspector.py   # orchestrator :8002 (not :8000)

Start the swarm before the orchestrator. Do not run ``run_all.py`` at the same time
(port 8000 conflict).

**Mailbox workflow (0.24.0):**
1. Run this script (Python **3.10–3.13** recommended for uAgents 0.24).
2. Copy the **Local Agent Inspector** URL from the log (or use the printed
   ``agentverse.ai/inspect/?uri=…&address=…`` link).
3. Open it in the browser → **Connect** → **Mailbox** to link mailbox in Agentverse.
4. Leave this process running so the agent stays **Active** in Agentverse My Agents;
   the mailbox client polls while you are online.

**Network:** defaults to Fetch **testnet** (Almanac). Set ``ORCHESTRATOR_NETWORK=mainnet``
if your wallet is funded.

**Optional:** ``AGENTVERSE_API_KEY`` (from Agentverse profile) is for *programmatic*
mailbox setup in some Fetch docs—not required for the Inspector Connect path above.

Optional env:
  ORCHESTRATOR_INSPECTOR_PORT=8002
  ORCHESTRATOR_NETWORK=mainnet
  ORCHESTRATOR_AGENTVERSE=...   # override Agentverse base URL if needed
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Repo root: port-power-nexus/ -> beachhack_2026/
_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env", override=True)

_port = os.getenv("ORCHESTRATOR_INSPECTOR_PORT", "8002").strip()
if not _port.isdigit():
    _port = "8002"
os.environ["ORCHESTRATOR_PORT"] = _port
# Always align submit URL with this process port (Inspector link + mailbox both need correct :port/submit).
os.environ["BUREAU_SUBMIT_URL"] = f"http://127.0.0.1:{_port}/submit"

# Import after env so chat.py builds Agent with port + matching submit URL.
from agents.orchestrator.agent import orchestrator_agent


def main() -> None:
    print(
        "\n[i] uAgents 0.24: mailbox=True | Open the **Local Agent Inspector** URL from the "
        "next log lines → Connect → Mailbox | Keep this process running for Agentverse "
        "Active status | testnet default (override ORCHESTRATOR_NETWORK if needed)\n",
        file=sys.stderr,
    )
    orchestrator_agent.run()


if __name__ == "__main__":
    main()
