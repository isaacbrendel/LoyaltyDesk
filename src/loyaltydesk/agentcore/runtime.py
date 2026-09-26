"""AgentCore-compatible runtime entrypoint."""

from __future__ import annotations

from typing import Any

from loyaltydesk.agentcore.manifest import get_manifest
from loyaltydesk.agentcore.policy import allow_request, default_scopes, requires_hitl
from loyaltydesk.agents.graph import run_agent
from loyaltydesk.guardrails.pipeline import apply_input_guardrails
from loyaltydesk.hitl import HITL_STORE


async def invoke(
    prompt: str,
    *,
    session_id: str = "runtime",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Package-level invoke used by local runtime and (conceptually) AgentCore."""
    context = context or {}
    allowed, notes = allow_request(prompt)
    if not allowed:
        return {
            "blocked": True,
            "notes": notes,
            "manifest": get_manifest()["name"],
        }

    guard = apply_input_guardrails(prompt)
    scopes = set(context.get("scopes") or default_scopes())
    state, tracer = await run_agent(
        guard.text,
        session_id=session_id,
        granted_scopes=scopes,
        force_hitl=requires_hitl(prompt) or bool(context.get("force_hitl")),
    )
    answer = state.get("answer")
    payload: dict[str, Any] = {
        "blocked": False,
        "run_id": tracer.run_id,
        "answer": answer.model_dump(mode="json") if answer else None,
        "handoffs": state.get("handoffs") or [],
        "reflection": state.get("reflection"),
        "hitl": state.get("hitl"),
        "traces": tracer.as_dicts(),
        "manifest": get_manifest()["name"],
    }
    if state.get("hitl") and state["hitl"].get("status") == "pending":
        HITL_STORE.create(
            run_id=tracer.run_id,
            session_id=session_id,
            question=prompt,
            proposal=payload,
        )
    return payload
