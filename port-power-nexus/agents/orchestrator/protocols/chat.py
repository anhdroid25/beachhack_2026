"""
ASI:One / Agentverse Chat Protocol (mandatory) + internal swarm protocol.

Uses `uagents_core.contrib.protocols.chat` (ChatMessage, ChatAcknowledgement).
Downstream messages use `shared.models` (same types as grid / terminal agents).

**uAgents 0.24.0 mailbox (Fetch.ai docs):** initialize with ``mailbox=True`` (this
module does that). Run the agent locally; use the **Local Agent Inspector** URL from
the logs (``…/inspect/?uri=…&address=…``). In Agentverse, open that link, click
**Connect**, choose **Mailbox**, and finish the link. Keep the process running so the
agent stays active in Agentverse; the mailbox client will pick up messages. Optional
``agentverse=`` can override the Agentverse base URL via ``ORCHESTRATOR_AGENTVERSE``.
Programmatic mailbox credentials (e.g. ``AGENTVERSE_API_KEY`` from your Agentverse
profile) are only needed if you configure mailbox outside Inspector—PyPI 0.24 does not
use that env var in ``Agent()``; the Inspector path is the supported default.

**Ports and mailbox (one machine):** Only this orchestrator uses ``mailbox=True``.
It still runs an ASGI server on ``ORCHESTRATOR_PORT`` / ``ORCHESTRATOR_INSPECTOR_PORT``
(default **8002**) so **Local Agent Inspector** can POST to ``/submit`` during setup.
Grid, trucks, and terminal use **HTTP submit** (``mailbox=False`` / omitted) and **must
each use a different port** (e.g. Bureau :8000 for swarm, grid :8001, terminal :8010,
trucks :8011–8013; orchestrator **8002** — do not reuse a port for two processes).
"""
import inspect
import os
import re
import time
from datetime import datetime
from urllib.parse import quote
from typing import Literal, Optional
from uuid import uuid4

import shared.env_loader  # noqa: F401 — repo root `.env` before config

from pydantic import BaseModel
from uagents import Agent, Context, Protocol
from uagents_core.types import DeliveryStatus
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from shared.config import load_orchestrator_settings
from shared.models import (
    AgentErrorResponse,
    AuctionStarted,
    FinalAssignmentResponse,
    StartAuctionRequest,
    TruckStatusRequest,
    TruckStatusResponse,
)

SETTINGS = load_orchestrator_settings()

# Orchestrator always uses Agentverse mailbox (not a direct HTTP submit endpoint).
_ORCH_MAILBOX = True
_ORCH_ENDPOINT = None  # never use ORCHESTRATOR_ENDPOINT for this agent; uAgents mailbox URL only


def _local_submit_url_for_inspector() -> str:
    """Submit URL for Local Agent Inspector (must match the process HTTP port)."""
    port_raw = os.getenv("ORCHESTRATOR_PORT", "").strip()
    if port_raw.isdigit():
        return f"http://127.0.0.1:{int(port_raw)}/submit"
    submit = os.getenv("BUREAU_SUBMIT_URL", "http://127.0.0.1:8000/submit").replace(
        "localhost", "127.0.0.1"
    )
    return submit


def _agentverse_inspector_url(agent_address: str) -> str:
    """Local Agent Inspector (open while run_all is running). Uses 127.0.0.1 for browser LNA."""
    submit = _local_submit_url_for_inspector()
    return (
        "https://agentverse.ai/inspect/?uri="
        + quote(submit, safe="")
        + "&address="
        + agent_address
    )
_agent_kwargs = {
    "name": "Logistics_Orchestrator",
    "seed": os.getenv("ORCHESTRATOR_SEED", "logistics_orchestrator_seed"),
    "store_message_history": True,
}


def _apply_mailbox_to_agent_kwargs(kwargs: dict) -> None:
    """Use mailbox API-key style only if the installed uAgents supports `mailbox_auth`."""
    params = inspect.signature(Agent.__init__).parameters
    key = os.getenv("ORCHESTRATOR_MAILBOX_KEY", "").strip()
    auth = os.getenv("ORCHESTRATOR_MAILBOX_AUTH", "").strip()
    if "mailbox_auth" in params and key and auth:
        kwargs["mailbox"] = f"{key}@agentverse.ai"
        kwargs["mailbox_auth"] = auth
    else:
        kwargs["mailbox"] = True


_apply_mailbox_to_agent_kwargs(_agent_kwargs)

_agentverse_url = os.getenv("ORCHESTRATOR_AGENTVERSE", "").strip()
if _agentverse_url:
    _agent_kwargs["agentverse"] = _agentverse_url


def _orchestrator_network() -> str:
    """Fetch ledger network. Defaults to testnet so Almanac contract registration can use testnet FET."""
    raw = os.getenv("ORCHESTRATOR_NETWORK", "").strip().lower()
    if raw in ("mainnet", "testnet"):
        return raw
    return "testnet"


_agent_kwargs["network"] = _orchestrator_network()
# Set only for standalone runs (e.g. run_orchestrator_for_inspector.py). Bureau + run_all omit this.
_orch_port_raw = os.getenv("ORCHESTRATOR_PORT", "").strip()
if _orch_port_raw.isdigit():
    _agent_kwargs["port"] = int(_orch_port_raw)

orchestrator_agent = Agent(**_agent_kwargs)

chat_protocol = Protocol(spec=chat_protocol_spec)
swarm_protocol = Protocol(name="port_power_swarm", version="0.1.0")

IntentType = Literal["start_auction_for_truck", "get_truck_status", "unknown"]
PENDING_INDEX_KEY = "pending_request_ids"

ORCHESTRATOR_HELLO_TEXT = SETTINGS.hello_text
ORCHESTRATOR_OUTBOUND_TIMEOUT_SECONDS = SETTINGS.outbound_timeout_seconds

TRUCK_PATTERN = re.compile(r"\btruck[_\-\s]?(\d{1,2})\b", re.IGNORECASE)
# Match demo fleet names → same ids the grid uses in StartAuctionRequest
_ALIAS_TO_TRUCK_ID = {
    "amazon": "Truck_01",
    "fedex": "Truck_02",
    "ups": "Truck_03",
}
AUCTION_KEYWORDS = {"charge", "charging", "slot", "auction", "bid", "cleanest"}
STATUS_KEYWORDS = {"status", "state", "progress", "update"}
SUSTAINABILITY_KEYWORDS = {"sustainable", "renewable", "clean", "cleanest"}


class ParsedCommand(BaseModel):
    intent: IntentType
    target_truck: Optional[str] = None
    requested_goal: Optional[str] = None
    original_text: str


def extract_text(msg: ChatMessage) -> str:
    chunks = []
    for item in msg.content:
        if isinstance(item, TextContent):
            chunks.append(item.text)
        elif isinstance(item, EndSessionContent):
            return ""
    return " ".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()


def strip_agent_mentions(text: str) -> str:
    return " ".join(token for token in text.split() if not token.startswith("@")).strip()


def create_text_chat(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text)],
    )


def normalize_truck_id(message: str) -> Optional[str]:
    match = TRUCK_PATTERN.search(message)
    if match:
        return f"Truck_{int(match.group(1)):02d}"
    lowered = message.lower()
    if "amazon_truck" in lowered.replace(" ", "") or re.search(
        r"\bamazon\b", lowered
    ):
        return _ALIAS_TO_TRUCK_ID["amazon"]
    if "fedex_truck" in lowered.replace(" ", "") or re.search(r"\bfedex\b", lowered):
        return _ALIAS_TO_TRUCK_ID["fedex"]
    if "ups_truck" in lowered.replace(" ", "") or re.search(
        r"\bups\b", lowered
    ):
        return _ALIAS_TO_TRUCK_ID["ups"]
    return None


def extract_goal(message: str) -> Optional[str]:
    lowered = message.lower()
    if any(word in lowered for word in SUSTAINABILITY_KEYWORDS):
        return "sustainable_charging"
    if any(word in lowered for word in {"fast", "urgent", "priority"}):
        return "priority_dispatch"
    if any(word in lowered for word in AUCTION_KEYWORDS):
        return "charge_slot"
    return None


def parse_command(message: str) -> ParsedCommand:
    lowered = message.lower()
    truck_id = normalize_truck_id(message)
    goal = extract_goal(message)

    if truck_id and any(word in lowered for word in STATUS_KEYWORDS):
        return ParsedCommand(
            intent="get_truck_status",
            target_truck=truck_id,
            requested_goal=goal,
            original_text=message,
        )

    if truck_id and any(word in lowered for word in AUCTION_KEYWORDS):
        return ParsedCommand(
            intent="start_auction_for_truck",
            target_truck=truck_id,
            requested_goal=goal,
            original_text=message,
        )

    return ParsedCommand(
        intent="unknown",
        target_truck=truck_id,
        requested_goal=goal,
        original_text=message,
    )


def is_handshake(message: str) -> bool:
    return message.strip().lower() in {"hello", "hi", "ping", "test", "handshake"}


def format_unknown_response(command: ParsedCommand) -> str:
    lowered = command.original_text.lower()
    truck_hint = (
        f" I recognized {command.target_truck}, but I still need a charging or status request."
        if command.target_truck
        else ""
    )
    wants_auction = any(w in lowered for w in AUCTION_KEYWORDS)
    wants_status = any(w in lowered for w in STATUS_KEYWORDS)
    if wants_auction and not command.target_truck:
        return (
            "To **start an auction**, I need **which truck** to prioritize. "
            "Say **Truck_01** or **truck 1**, or **amazon** / **fedex** / **ups**. "
            'Example: "Start an auction for Truck_01" or "charging auction for amazon".'
        )
    if wants_status and not command.target_truck:
        return (
            "For **status**, name the truck: e.g. **Truck_02**, **truck 2**, or **fedex**."
        )
    return (
        "I can coordinate charging requests for the Port-Power Nexus swarm."
        f"{truck_hint} Try: \"what is the status of Truck_02\" or "
        "\"find the cleanest charging slot for Truck_07\" (or use **amazon** / **fedex** / **ups**)."
    )


def format_assignment_response(
    response: FinalAssignmentResponse, requested_goal: Optional[str]
) -> str:
    goal = requested_goal or "general_dispatch"
    parts = [
        f"Truck: {response.truck_id}",
        f"Interpreted goal: {goal}",
        f"Status: {response.status}",
        f"Reasoning: {response.decision_summary}",
    ]
    if response.bay:
        parts.append(f"Assigned bay: {response.bay}")
    if response.price is not None:
        parts.append(f"Clearing price: ${response.price:.2f}")
    if response.tx_hash:
        parts.append(f"TX hash: {response.tx_hash}")
    return "\n".join(parts)


def format_truck_status_response(response: TruckStatusResponse) -> str:
    parts = [
        f"Truck: {response.truck_id}",
        f"Status: {response.truck_status}",
    ]
    if response.state_of_charge is not None:
        parts.append(f"State of charge: {response.state_of_charge}%")
    if response.distance_to_port is not None:
        parts.append(f"Distance to port: {response.distance_to_port} miles")
    if response.bay:
        parts.append(f"Assigned bay: {response.bay}")
    return "\n".join(parts)


def format_error_response(response: AgentErrorResponse) -> str:
    return (
        f"The swarm reported a failure from {response.source_agent}. "
        f"Details: {response.error_message}"
    )


def format_timeout_response(command: ParsedCommand) -> str:
    if command.intent == "start_auction_for_truck":
        return (
            f"The auction request for {command.target_truck} was dispatched, but the Grid Agent "
            "did not return a final assignment before the timeout window closed."
        )
    if command.intent == "get_truck_status":
        return (
            f"The status request for {command.target_truck} was dispatched, but the truck status "
            "agent did not answer before the timeout window closed."
        )
    return "The orchestrator timed out waiting for a downstream swarm response."


def _pending_key(request_id: str) -> str:
    return f"pending_request:{request_id}"


def save_pending_request(
    ctx: Context, request_id: str, sender: str, command: ParsedCommand
) -> None:
    pending = {
        "request_id": request_id,
        "sender": sender,
        "intent": command.intent,
        "target_truck": command.target_truck,
        "requested_goal": command.requested_goal,
        "original_text": command.original_text,
        "created_at": time.time(),
        "expires_at": time.time() + ORCHESTRATOR_OUTBOUND_TIMEOUT_SECONDS,
        "stage": "dispatched",
    }
    ctx.storage.set(_pending_key(request_id), pending)
    pending_ids = ctx.storage.get(PENDING_INDEX_KEY) or []
    if request_id not in pending_ids:
        pending_ids.append(request_id)
        ctx.storage.set(PENDING_INDEX_KEY, pending_ids)


def get_pending_request(ctx: Context, request_id: str) -> Optional[dict]:
    return ctx.storage.get(_pending_key(request_id))


def update_pending_stage(ctx: Context, request_id: str, stage: str) -> None:
    pending = get_pending_request(ctx, request_id)
    if not pending:
        return
    pending["stage"] = stage
    ctx.storage.set(_pending_key(request_id), pending)


def remove_pending_request(ctx: Context, request_id: str) -> None:
    ctx.storage.remove(_pending_key(request_id))
    pending_ids = ctx.storage.get(PENDING_INDEX_KEY) or []
    if request_id in pending_ids:
        pending_ids.remove(request_id)
        ctx.storage.set(PENDING_INDEX_KEY, pending_ids)


def parsed_command_from_pending(pending: dict) -> ParsedCommand:
    return ParsedCommand(
        intent=pending["intent"],
        target_truck=pending.get("target_truck"),
        requested_goal=pending.get("requested_goal"),
        original_text=pending.get("original_text", ""),
    )


async def route_command(ctx: Context, sender: str, command: ParsedCommand) -> str:
    if command.intent == "unknown" or not command.target_truck:
        return format_unknown_response(command)

    if command.intent == "get_truck_status":
        request_id = str(uuid4())
        request = TruckStatusRequest(
            request_id=request_id,
            truck_id=command.target_truck,
            reply_to=ctx.agent.address,
            timestamp=datetime.utcnow(),
        )
        status = await ctx.send(
            SETTINGS.addresses.truck_status_agent,
            request,
            timeout=SETTINGS.outbound_timeout_seconds,
        )
        if status.status == DeliveryStatus.FAILED:
            return (
                f"I could not reach the truck status agent for {command.target_truck}. "
                f"Details: {status.detail}."
            )
        save_pending_request(ctx, request_id, sender, command)
        return (
            f"I've dispatched a truck status request for {command.target_truck}. "
            "I will return the latest charging state as soon as the swarm responds."
        )

    request_id = str(uuid4())
    request = StartAuctionRequest(
        request_id=request_id,
        truck_id=command.target_truck,
        requested_goal=command.requested_goal,
        original_text=command.original_text,
        reply_to=ctx.agent.address,
        timestamp=datetime.utcnow(),
    )
    status = await ctx.send(
        SETTINGS.addresses.grid_agent,
        request,
        timeout=SETTINGS.outbound_timeout_seconds,
    )
    if status.status == DeliveryStatus.FAILED:
        return (
            f"I could not reach the Grid Agent for {command.target_truck}. "
            f"Details: {status.detail}."
        )
    save_pending_request(ctx, request_id, sender, command)
    return (
        f"I've dispatched an auction request for {command.target_truck}. "
        "I will return the reasoning, assigned bay, and TX hash as soon as the swarm responds."
    )


@orchestrator_agent.on_event("startup")
async def startup(ctx: Context) -> None:
    # ctx.agent is AgentRepresentation — use the real Agent for mailbox_client.
    if _ORCH_MAILBOX and getattr(orchestrator_agent, "mailbox_client", None) is None:
        ctx.logger.error(
            "[Orchestrator] Mailbox is enabled but no mailbox client was created. "
            "uAgents only enables mailbox when endpoints include the Agentverse mailbox URL — "
            "do not pass `endpoint=` (ORCHESTRATOR_ENDPOINT / submit URL) together with mailbox. "
            "Unset ORCHESTRATOR_ENDPOINT or run via run_orchestrator_for_inspector.py without "
            "injecting a submit URL into the Agent constructor."
        )
    if "mailbox_auth" not in inspect.signature(Agent.__init__).parameters and (
        os.getenv("ORCHESTRATOR_MAILBOX_KEY", "").strip()
        or os.getenv("ORCHESTRATOR_MAILBOX_AUTH", "").strip()
    ):
        ctx.logger.warning(
            "[Orchestrator] ORCHESTRATOR_MAILBOX_KEY/AUTH are set but this uAgents build "
            "has no mailbox_auth; using mailbox=True. Complete Connect→Mailbox in Inspector, "
            "or upgrade uAgents when that API ships."
        )
    ctx.logger.info(
        f"[Orchestrator] Chat Protocol + swarm | address={ctx.agent.address} "
        f"network={_orchestrator_network()} mailbox={_ORCH_MAILBOX} "
        f"endpoint={_ORCH_ENDPOINT or 'mailbox'} "
        f"grid={SETTINGS.addresses.grid_agent} "
        f"truck_status={SETTINGS.addresses.truck_status_agent}"
    )
    # Local Agent Inspector does not support multi-agent Bureaus (run_all.py).
    if _orch_port_raw.isdigit():
        ctx.logger.info(
            f"[Orchestrator] Local Agent Inspector (single process): "
            f"{_agentverse_inspector_url(ctx.agent.address)}"
        )
    else:
        ctx.logger.info(
            "[Orchestrator] Agentverse Inspector does not support Agent Bureaus — "
            "run_all.py cannot be used with Connect in Inspector. "
            "For mailbox / Inspector testing, use: python run_orchestrator_for_inspector.py "
            "(separate terminal; full swarm still needs run_all for grid/trucks/terminal)."
        )


@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.utcnow(),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    text = extract_text(msg)
    if not text:
        await ctx.send(sender, create_text_chat("Session closed."))
        return

    cleaned_text = strip_agent_mentions(text)
    command = parse_command(cleaned_text)
    ctx.logger.info(
        "hosted_chat_received "
        f"sender={sender} "
        f"intent={command.intent} "
        f"truck={command.target_truck} "
        f"goal={command.requested_goal}"
    )

    if is_handshake(cleaned_text):
        await ctx.send(sender, create_text_chat(ORCHESTRATOR_HELLO_TEXT))
        return

    reply = await route_command(ctx, sender, command)
    await ctx.send(sender, create_text_chat(reply))


@swarm_protocol.on_message(AuctionStarted)
async def handle_auction_started(ctx: Context, sender: str, msg: AuctionStarted):
    pending = get_pending_request(ctx, msg.request_id)
    ctx.logger.info(
        f"auction_started sender={sender} truck={msg.truck_id} status={msg.status}"
    )
    if not pending:
        return
    update_pending_stage(ctx, msg.request_id, "auction_started")
    await ctx.send(
        pending["sender"],
        create_text_chat(f"Auction started for {msg.truck_id}. {msg.note}"),
    )


@swarm_protocol.on_message(TruckStatusResponse)
async def handle_truck_status_response(
    ctx: Context, sender: str, msg: TruckStatusResponse
):
    pending = get_pending_request(ctx, msg.request_id)
    ctx.logger.info(
        f"truck_status_response sender={sender} truck={msg.truck_id} status={msg.truck_status}"
    )
    if not pending:
        return
    await ctx.send(
        pending["sender"], create_text_chat(format_truck_status_response(msg))
    )
    remove_pending_request(ctx, msg.request_id)


@swarm_protocol.on_message(FinalAssignmentResponse)
async def handle_final_assignment(
    ctx: Context, sender: str, msg: FinalAssignmentResponse
):
    pending = get_pending_request(ctx, msg.request_id)
    ctx.logger.info(
        f"final_assignment sender={sender} truck={msg.truck_id} status={msg.status}"
    )
    if not pending:
        return
    command = parsed_command_from_pending(pending)
    await ctx.send(
        pending["sender"],
        create_text_chat(format_assignment_response(msg, command.requested_goal)),
    )
    remove_pending_request(ctx, msg.request_id)


@swarm_protocol.on_message(AgentErrorResponse)
async def handle_agent_error(ctx: Context, sender: str, msg: AgentErrorResponse):
    pending = get_pending_request(ctx, msg.request_id)
    ctx.logger.info(
        f"agent_error sender={sender} source={msg.source_agent} detail={msg.error_message}"
    )
    if not pending:
        return
    await ctx.send(pending["sender"], create_text_chat(format_error_response(msg)))
    remove_pending_request(ctx, msg.request_id)


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug(f"ack_received sender={sender} msg_id={msg.acknowledged_msg_id}")


@swarm_protocol.on_interval(period=5.0)
async def timeout_pending_requests(ctx: Context):
    pending_ids = list(ctx.storage.get(PENDING_INDEX_KEY) or [])
    now = time.time()
    for request_id in pending_ids:
        pending = get_pending_request(ctx, request_id)
        if not pending:
            remove_pending_request(ctx, request_id)
            continue
        if pending.get("expires_at", now + 1) > now:
            continue
        command = parsed_command_from_pending(pending)
        await ctx.send(
            pending["sender"],
            create_text_chat(format_timeout_response(command)),
        )
        remove_pending_request(ctx, request_id)


orchestrator_agent.include(chat_protocol, publish_manifest=True)
orchestrator_agent.include(swarm_protocol, publish_manifest=True)
