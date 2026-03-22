import os
import re
from dataclasses import dataclass
from datetime import datetime
import time
from typing import Literal, Optional
from uuid import uuid4

from uagents import Agent, Context, Model
from uagents_core.types import DeliveryStatus

from agents.orchestrator.protocols.chat import chat_protocol, swarm_protocol
from shared.config import load_orchestrator_settings
from shared.agent_net import submit_endpoint
from shared.models import (
    AgentErrorResponse,
    AuctionStarted,
    FinalAssignmentResponse,
    StartAuctionRequest,
    TruckStatusRequest,
    TruckStatusResponse,
)


IntentType = Literal["start_auction_for_truck", "get_truck_status", "unknown"]

TRUCK_PATTERN = re.compile(r"\btruck[_\-\s]?(\d{1,2})\b", re.IGNORECASE)
AUCTION_KEYWORDS = {"charge", "charging", "slot", "auction", "bid", "cleanest"}
STATUS_KEYWORDS = {"status", "state", "progress", "update"}
SUSTAINABILITY_KEYWORDS = {"sustainable", "renewable", "clean", "cleanest"}


class OrchestratorChatMessage(Model):
    message: str
    thread_id: Optional[str] = None
    user_id: Optional[str] = None


class OrchestratorChatResponse(Model):
    message: str
    status: str = "ok"


@dataclass(frozen=True)
class ParsedCommand:
    intent: IntentType
    target_truck: Optional[str]
    requested_goal: Optional[str]
    original_text: str


PENDING_INDEX_KEY = "pending_request_ids"


SETTINGS = load_orchestrator_settings()

ORCHESTRATOR_PORT = int(os.environ.get("ORCHESTRATOR_PORT", "8002"))

# Identity (agent1q…) comes from name + seed — NOT from ORCHESTRATOR_PORT. If ASI:One / Agentverse
# still points at an old address, either restore ORCHESTRATOR_SEED to match or re-register the new
# address from the startup log.
ORCHESTRATOR_SEED = os.environ.get(
    "ORCHESTRATOR_SEED",
    "ahoiwenaow",
)

# `publish_manifest=True` is required for ASI:One / Agentverse protocol discovery; it can also
# contact peer HTTP endpoints at startup → "dispenser" errors if trucks are offline. Default true
# for ASI; set ORCHESTRATOR_PUBLISH_MANIFEST=false for local dev without the fleet.
_ORCH_PUBLISH_MANIFEST = (
    os.environ.get("ORCHESTRATOR_PUBLISH_MANIFEST", "true").strip().lower()
    in ("1", "true", "yes")
)

# Mailbox: do NOT pass `endpoint=http://.../submit` together with `mailbox=True` — uAgents treats
# a custom endpoint as overriding mailbox, so the MailboxClient never starts. Use mailbox-only
# endpoints from Agentverse; the process still binds ORCHESTRATOR_PORT for the agent inspector.
# Set ORCHESTRATOR_MAILBOX=false to use plain local /submit only (no Agentverse mailbox).
_ORCH_MAILBOX = os.environ.get("ORCHESTRATOR_MAILBOX", "true").strip().lower() in (
    "1",
    "true",
    "yes",
)
_orchestrator_endpoint = None if _ORCH_MAILBOX else submit_endpoint(ORCHESTRATOR_PORT)

orchestrator_agent = Agent(
    name="Logistics_Orchestrator",
    seed=ORCHESTRATOR_SEED,
    port=ORCHESTRATOR_PORT,
    endpoint=_orchestrator_endpoint,
    mailbox=_ORCH_MAILBOX,
)
orchestrator_agent.include(chat_protocol, publish_manifest=_ORCH_PUBLISH_MANIFEST)
orchestrator_agent.include(swarm_protocol, publish_manifest=_ORCH_PUBLISH_MANIFEST)


def parse_command(message: str) -> ParsedCommand:
    lowered = message.lower()
    truck_id = normalize_truck_id(message)
    goal = extract_goal(message)

    if "start auction" in lowered:
        tid = truck_id if truck_id else "all"
        return ParsedCommand("start_auction_for_truck", tid, goal, message)

    if truck_id and any(word in lowered for word in STATUS_KEYWORDS):
        return ParsedCommand("get_truck_status", truck_id, goal, message)

    if truck_id and any(word in lowered for word in AUCTION_KEYWORDS):
        return ParsedCommand("start_auction_for_truck", truck_id, goal, message)

    return ParsedCommand("unknown", truck_id, goal, message)


def normalize_truck_id(message: str) -> Optional[str]:
    match = TRUCK_PATTERN.search(message)
    if not match:
        return None
    return f"Truck_{int(match.group(1)):02d}"


def extract_goal(message: str) -> Optional[str]:
    lowered = message.lower()
    if any(word in lowered for word in SUSTAINABILITY_KEYWORDS):
        return "sustainable_charging"
    if any(word in lowered for word in {"fast", "urgent", "priority"}):
        return "priority_dispatch"
    if any(word in lowered for word in AUCTION_KEYWORDS):
        return "charge_slot"
    return None


def format_unknown_response(command: ParsedCommand) -> str:
    truck_hint = (
        f" I recognized {command.target_truck}, but I still need a charging or status request."
        if command.target_truck
        else ""
    )
    return (
        "I can coordinate charging requests for the Port-Power Nexus swarm."
        f"{truck_hint} Try: \"start auction\" (whole fleet), "
        "\"start auction for Truck_01\" (one truck), or \"what is the status of Truck_02\"."
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
            f"I sent the auction request for {command.target_truck}, but the swarm did not "
            "return a final assignment before the timeout window closed."
        )
    if command.intent == "get_truck_status":
        return (
            f"I requested the latest status for {command.target_truck}, but the status agent "
            "did not answer before the timeout window closed."
        )
    return "The orchestrator timed out waiting for a downstream swarm response."


def _pending_key(request_id: str) -> str:
    return f"pending_request:{request_id}"


def save_pending_request(
    ctx: Context,
    request_id: str,
    sender: str,
    command: ParsedCommand,
) -> None:
    pending = {
        "request_id": request_id,
        "sender": sender,
        "intent": command.intent,
        "target_truck": command.target_truck,
        "requested_goal": command.requested_goal,
        "original_text": command.original_text,
        "created_at": time.time(),
        "expires_at": time.time() + SETTINGS.outbound_timeout_seconds,
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
    if command.intent == "unknown":
        return format_unknown_response(command)

    if command.intent == "get_truck_status" and not command.target_truck:
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
            sync=False,
            timeout=SETTINGS.outbound_timeout_seconds,
        )
        if status.status == DeliveryStatus.FAILED:
            return (
                f"I could not reach the truck status agent for {command.target_truck}. "
                f"Details: {status.detail}."
            )
        save_pending_request(ctx, request_id, sender, command)
        return (
            f"I've asked the swarm for the latest status of {command.target_truck}. "
            "I will return the current charging state when the truck agent responds."
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
        sync=False,
        timeout=SETTINGS.outbound_timeout_seconds,
    )
    if status.status == DeliveryStatus.FAILED:
        return (
            f"I could not reach the Grid Agent for {command.target_truck}. "
            f"Details: {status.detail}."
        )
    save_pending_request(ctx, request_id, sender, command)
    scope = (
        "all trucks"
        if (command.target_truck or "").lower() == "all"
        else command.target_truck
    )
    return (
        f"I've asked the Grid Agent to start an auction for {scope}. "
        "I will format the bay assignment, reasoning, and TX hash as soon as the swarm replies."
    )


@orchestrator_agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(
        f"Orchestrator started address={ctx.agent.address} "
        f"mailbox={_ORCH_MAILBOX} "
        f"publish_manifest={_ORCH_PUBLISH_MANIFEST} "
        f"grid={SETTINGS.addresses.grid_agent} "
        f"terminal={SETTINGS.addresses.terminal_agent} "
        f"truck_status={SETTINGS.addresses.truck_status_agent} "
        f"fleet={list(SETTINGS.addresses.truck_agents)}"
    )


@orchestrator_agent.on_message(model=OrchestratorChatMessage, replies={OrchestratorChatResponse}, allow_unverified=True)
async def handle_chat(ctx: Context, sender: str, msg: OrchestratorChatMessage):
    cleaned = " ".join(token for token in msg.message.split() if not token.startswith("@")).strip()
    if cleaned.lower() in {"hello", "hi", "ping", "test", "handshake"}:
        await ctx.send(sender, OrchestratorChatResponse(message=SETTINGS.hello_text))
        return

    command = parse_command(cleaned)
    reply = await route_command(ctx, sender, command)
    await ctx.send(sender, OrchestratorChatResponse(message=reply))


if __name__ == "__main__":
    orchestrator_agent.run()
