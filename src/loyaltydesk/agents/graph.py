"""LangGraph supervisor + subagents for loyalty analyst workflows."""

from __future__ import annotations

from typing import Any, Iterator

from langgraph.graph import END, START, StateGraph

from loyaltydesk.agentcore.gateway import GATEWAY
from loyaltydesk.agentcore.policy import requires_hitl
from loyaltydesk.agents.planner import demo_tool_calls, maybe_llm_synthesize, plan_route
from loyaltydesk.agents.reflect import reflect_on_answer
from loyaltydesk.agents.state import AgentState
from loyaltydesk.guardrails.pipeline import apply_output_guardrails
from loyaltydesk.guardrails.tool_scope import ANALYST_SCOPES
from loyaltydesk.models import AgentRole
from loyaltydesk.observability.tracing import TraceRecorder


def _run_calls(
    role: AgentRole,
    question: str,
    granted_scopes: set[str],
    tracer: TraceRecorder,
) -> dict[str, Any]:
    calls = demo_tool_calls(role, question)
    tool_results: list[dict[str, Any]] = []
    sql_used: list[str] = []
    citations: list[dict[str, Any]] = []
    intermediate: list[str] = []

    for call in calls:
        name = call["name"]
        args = call["args"]
        tracer.emit("tool.start", role=role, tool=name, args=args)
        payload = GATEWAY.call(name, args, granted_scopes=granted_scopes)
        payload["agent"] = role.value
        tool_results.append(payload)
        if payload.get("ok"):
            result = payload.get("result")
            intermediate.append(f"{role.value}:{name}:ok:attempts={payload.get('attempts', 1)}")
            if name == "run_sql" and isinstance(result, dict):
                sql_used.append(result.get("sql", args.get("sql", "")))
            if name == "ask_semantic" and isinstance(result, dict) and result.get("resolved"):
                sql_used.append(result.get("compiled_sql", ""))
            if name == "search_knowledge" and isinstance(result, list):
                for hit in result:
                    citations.append(
                        {
                            "source": f"{hit['doc_id']}:{hit['section']}",
                            "snippet": hit["content"][:200],
                            "score": hit["score"],
                        }
                    )
            if name == "explain_loyalty_rule" and isinstance(result, dict):
                for cite in result.get("citations") or []:
                    citations.append(cite)
            tracer.emit(
                "tool.end",
                role=role,
                tool=name,
                ok=True,
                attempts=payload.get("attempts", 1),
            )
        else:
            intermediate.append(f"{role.value}:{name}:error:{payload.get('error')}")
            tracer.emit(
                "tool.end",
                role=role,
                tool=name,
                ok=False,
                error=payload.get("error"),
                attempts=payload.get("attempts", 1),
            )

    return {
        "tool_results": tool_results,
        "sql_used": sql_used,
        "citations": citations,
        "intermediate": intermediate,
    }


def build_graph(tracer: TraceRecorder | None = None):
    tracer = tracer or TraceRecorder()

    def supervisor(state: AgentState) -> dict[str, Any]:
        route = plan_route(state["question"])
        tracer.emit("supervisor.route", role=AgentRole.SUPERVISOR, route=[r.value for r in route])
        scopes = state.get("granted_scopes") or sorted(ANALYST_SCOPES)
        handoffs = [
            {
                "from": AgentRole.SUPERVISOR.value,
                "to": role.value,
                "reason": f"Route matched for: {state['question'][:120]}",
            }
            for role in route
        ]
        return {"route": route, "granted_scopes": scopes, "handoffs": handoffs}

    def sql_analyst(state: AgentState) -> dict[str, Any]:
        if AgentRole.SQL_ANALYST not in state.get("route", []):
            return {}
        tracer.emit("agent.enter", role=AgentRole.SQL_ANALYST)
        return _run_calls(
            AgentRole.SQL_ANALYST,
            state["question"],
            set(state.get("granted_scopes") or ANALYST_SCOPES),
            tracer,
        )

    def knowledge(state: AgentState) -> dict[str, Any]:
        if AgentRole.KNOWLEDGE not in state.get("route", []):
            return {}
        tracer.emit("agent.enter", role=AgentRole.KNOWLEDGE)
        return _run_calls(
            AgentRole.KNOWLEDGE,
            state["question"],
            set(state.get("granted_scopes") or ANALYST_SCOPES),
            tracer,
        )

    def loyalty_logic(state: AgentState) -> dict[str, Any]:
        if AgentRole.LOYALTY_LOGIC not in state.get("route", []):
            return {}
        tracer.emit("agent.enter", role=AgentRole.LOYALTY_LOGIC)
        return _run_calls(
            AgentRole.LOYALTY_LOGIC,
            state["question"],
            set(state.get("granted_scopes") or ANALYST_SCOPES),
            tracer,
        )

    async def synthesize(state: AgentState) -> dict[str, Any]:
        tracer.emit("synthesize.start", role=AgentRole.SUPERVISOR)
        answer = await maybe_llm_synthesize(
            state["question"],
            route=state.get("route") or [],
            tool_results=state.get("tool_results") or [],
            sql_used=state.get("sql_used") or [],
            citations=state.get("citations") or [],
        )
        answer = apply_output_guardrails(answer)
        patterns = ["supervisor_router", "tool_calling", "structured_output"]
        if state.get("handoffs"):
            patterns.append("subagent_handoff")
        answer = answer.model_copy(update={"patterns_used": patterns})
        tracer.emit(
            "synthesize.end",
            role=AgentRole.SUPERVISOR,
            confidence=answer.confidence,
            guarded=answer.guarded,
        )
        return {"answer": answer}

    def reflect(state: AgentState) -> dict[str, Any]:
        answer = state.get("answer")
        if answer is None:
            return {"reflection": {"verdict": "fail", "notes": ["No answer to reflect on."], "score": 0.0}}
        reflection = reflect_on_answer(
            state["question"],
            answer,
            tool_results=state.get("tool_results") or [],
        )
        tracer.emit("reflection", role=AgentRole.SUPERVISOR, **reflection)
        patterns = list(answer.patterns_used or [])
        if "reflection" not in patterns:
            patterns.append("reflection")
        updated = answer.model_copy(
            update={
                "confidence": reflection["adjusted_confidence"],
                "reflection_notes": reflection["notes"],
                "patterns_used": patterns,
            }
        )
        return {"answer": updated, "reflection": reflection}

    def hitl_gate(state: AgentState) -> dict[str, Any]:
        answer = state.get("answer")
        need = bool(state.get("force_hitl")) or requires_hitl(state["question"])
        if not need or answer is None:
            return {"hitl": {"status": "not_required"}}
        tracer.emit("hitl.pending", role=AgentRole.SUPERVISOR, question=state["question"])
        patterns = list(answer.patterns_used or [])
        if "human_in_the_loop" not in patterns:
            patterns.append("human_in_the_loop")
        updated = answer.model_copy(
            update={
                "hitl_status": "pending",
                "patterns_used": patterns,
                "recommended_actions": list(answer.recommended_actions)
                + ["Awaiting analyst approval before any program change is applied."],
                "summary": (
                    answer.summary
                    + " This proposal is gated for human-in-the-loop approval "
                    "(program mutation / production push)."
                ),
            }
        )
        return {
            "answer": updated,
            "hitl": {
                "status": "pending",
                "reason": "Program mutation or explicit approval requested.",
            },
        }

    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor)
    graph.add_node("sql_analyst", sql_analyst)
    graph.add_node("knowledge", knowledge)
    graph.add_node("loyalty_logic", loyalty_logic)
    graph.add_node("synthesize", synthesize)
    graph.add_node("reflect", reflect)
    graph.add_node("hitl_gate", hitl_gate)

    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "sql_analyst")
    graph.add_edge("sql_analyst", "knowledge")
    graph.add_edge("knowledge", "loyalty_logic")
    graph.add_edge("loyalty_logic", "synthesize")
    graph.add_edge("synthesize", "reflect")
    graph.add_edge("reflect", "hitl_gate")
    graph.add_edge("hitl_gate", END)

    return graph.compile(), tracer


async def run_agent(
    question: str,
    *,
    session_id: str = "default",
    granted_scopes: set[str] | None = None,
    force_hitl: bool = False,
) -> tuple[Any, TraceRecorder]:
    compiled, tracer = build_graph()
    tracer.emit("run.start", question=question, session_id=session_id)
    state = await compiled.ainvoke(
        {
            "question": question,
            "session_id": session_id,
            "tool_results": [],
            "sql_used": [],
            "citations": [],
            "intermediate": [],
            "handoffs": [],
            "force_hitl": force_hitl,
            "granted_scopes": sorted(granted_scopes or ANALYST_SCOPES),
        }
    )
    tracer.emit("run.end", ok=state.get("answer") is not None)
    tracer.persist()
    return state, tracer


def stream_status(question: str) -> Iterator[dict[str, Any]]:
    """Simple status stream for the UI when full token streaming is demo-mode."""
    route = plan_route(question)
    yield {"event": "route", "agents": [r.value for r in route]}
    for role in route:
        yield {"event": "handoff", "from": "supervisor", "to": role.value}
        yield {"event": "agent", "agent": role.value, "status": "running"}
        yield {"event": "agent", "agent": role.value, "status": "done"}
    yield {"event": "synthesize", "status": "running"}
    yield {"event": "reflection", "status": "running"}
    if requires_hitl(question):
        yield {"event": "hitl", "status": "pending"}
