"""LangGraph supervisor + subagents with checkpointer HITL (interrupt/Command).

HITL follows LangGraph docs:
https://docs.langchain.com/oss/python/langgraph/interrupts
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Iterator

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from loyaltydesk.agentcore.gateway import GATEWAY
from loyaltydesk.agentcore.policy import requires_hitl
from loyaltydesk.agents.planner import (
    demo_tool_calls,
    maybe_llm_synthesize,
    plan_route,
    skills_for_question,
)
from loyaltydesk.agents.reflect import reflect_on_answer
from loyaltydesk.agents.state import AgentState
from loyaltydesk.evals.metrics import score_answer
from loyaltydesk.guardrails.pipeline import apply_output_guardrails
from loyaltydesk.guardrails.tool_scope import ANALYST_SCOPES
from loyaltydesk.models import AgentRole
from loyaltydesk.observability.otel import OtelTracer
from loyaltydesk.observability.run_store import RUN_STORE, RunCard, now_iso
from loyaltydesk.observability.tracing import TraceRecorder

# Process-wide checkpointer so HITL can resume by thread_id (AgentCore Memory seam).
CHECKPOINTER = MemorySaver()


def _run_calls(
    role: AgentRole,
    question: str,
    granted_scopes: set[str],
    tracer: TraceRecorder,
    *,
    session_key: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    calls = demo_tool_calls(role, question, history=history)
    tool_results: list[dict[str, Any]] = []
    sql_used: list[str] = []
    citations: list[dict[str, Any]] = []
    intermediate: list[str] = []

    for call in calls:
        name = call["name"]
        args = call["args"]
        tracer.emit("tool.start", role=role, tool=name, args=args)
        payload = GATEWAY.call(
            name, args, granted_scopes=granted_scopes, session_key=session_key
        )
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
                "tool.end", role=role, tool=name, ok=True, attempts=payload.get("attempts", 1)
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
        history = state.get("history") or []
        route = plan_route(state["question"], history)
        skills = skills_for_question(state["question"])
        tracer.emit(
            "supervisor.route",
            role=AgentRole.SUPERVISOR,
            route=[r.value for r in route],
            skills=skills,
        )
        scopes = state.get("granted_scopes") or sorted(ANALYST_SCOPES)
        handoffs = [
            {
                "from": AgentRole.SUPERVISOR.value,
                "to": role.value,
                "reason": f"Route matched for: {state['question'][:120]}",
            }
            for role in route
        ]
        return {
            "route": route,
            "granted_scopes": scopes,
            "handoffs": handoffs,
            "skills_used": skills,
        }

    def sql_analyst(state: AgentState) -> dict[str, Any]:
        if AgentRole.SQL_ANALYST not in state.get("route", []):
            return {}
        tracer.emit("agent.enter", role=AgentRole.SQL_ANALYST)
        return _run_calls(
            AgentRole.SQL_ANALYST,
            state["question"],
            set(state.get("granted_scopes") or ANALYST_SCOPES),
            tracer,
            session_key=state.get("session_id") or "default",
            history=state.get("history") or [],
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
            session_key=state.get("session_id") or "default",
            history=state.get("history") or [],
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
            session_key=state.get("session_id") or "default",
            history=state.get("history") or [],
        )

    async def synthesize(state: AgentState) -> dict[str, Any]:
        tracer.emit("synthesize.start", role=AgentRole.SUPERVISOR)
        answer = await maybe_llm_synthesize(
            state["question"],
            route=state.get("route") or [],
            tool_results=state.get("tool_results") or [],
            sql_used=state.get("sql_used") or [],
            citations=state.get("citations") or [],
            history=state.get("history") or [],
        )
        answer = apply_output_guardrails(answer)
        patterns = ["supervisor_router", "tool_calling", "structured_output"]
        if state.get("handoffs"):
            patterns.append("subagent_handoff")
        metrics = score_answer(
            answer.model_dump(mode="json"),
            tool_results=state.get("tool_results") or [],
        )
        answer = answer.model_copy(
            update={
                "patterns_used": patterns,
                "guardrail_notes": list(answer.guardrail_notes)
                + [f"faithfulness={metrics['faithfulness']}", f"groundedness={metrics['groundedness']}"],
            }
        )
        tracer.emit(
            "synthesize.end",
            role=AgentRole.SUPERVISOR,
            confidence=answer.confidence,
            **metrics,
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
        """LangGraph-native HITL via interrupt() + checkpointer resume."""
        answer = state.get("answer")
        need = bool(state.get("force_hitl")) or requires_hitl(state["question"])
        if not need or answer is None:
            return {"hitl": {"status": "not_required"}}

        tracer.emit("hitl.interrupt", role=AgentRole.SUPERVISOR, question=state["question"])
        # Pause here — resume value becomes `decision` (LangGraph docs pattern).
        decision = interrupt(
            {
                "kind": "program_mutation_approval",
                "question": state["question"],
                "summary": answer.summary,
                "recommended_actions": answer.recommended_actions,
            }
        )
        approved = bool(
            (isinstance(decision, dict) and decision.get("approve"))
            or decision is True
            or str(decision).lower() in {"approve", "approved", "yes", "true"}
        )
        note = ""
        if isinstance(decision, dict):
            note = str(decision.get("note") or "")
        status = "approved" if approved else "rejected"
        patterns = list(answer.patterns_used or [])
        if "human_in_the_loop" not in patterns:
            patterns.append("human_in_the_loop")
        if "langgraph_interrupt" not in patterns:
            patterns.append("langgraph_interrupt")
        updated = answer.model_copy(
            update={
                "hitl_status": status,
                "patterns_used": patterns,
                "recommended_actions": list(answer.recommended_actions)
                + ([f"HITL {status}" + (f": {note}" if note else "")]),
                "summary": answer.summary + f" Human decision: {status}.",
            }
        )
        tracer.emit("hitl.resolved", role=AgentRole.SUPERVISOR, status=status, note=note)
        return {"answer": updated, "hitl": {"status": status, "note": note}}

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

    return graph.compile(checkpointer=CHECKPOINTER), tracer


def _thread_config(session_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


def _pending_hitl_patch(state: dict[str, Any]) -> dict[str, Any]:
    interrupted = bool(state.get("__interrupt__"))
    if not interrupted:
        return state
    answer = state.get("answer")
    if answer is not None:
        patterns = list(answer.patterns_used or [])
        for p in ("human_in_the_loop", "langgraph_interrupt"):
            if p not in patterns:
                patterns.append(p)
        state["answer"] = answer.model_copy(
            update={
                "hitl_status": "pending",
                "patterns_used": patterns,
                "summary": answer.summary
                + " Awaiting human-in-the-loop approval (LangGraph interrupt).",
                "recommended_actions": list(answer.recommended_actions)
                + ["Awaiting analyst approval before any program change is applied."],
            }
        )
    state["hitl"] = {
        "status": "pending",
        "interrupt": [getattr(i, "value", i) for i in (state.get("__interrupt__") or [])],
    }
    return state


def _record_run(
    *,
    question: str,
    session_id: str,
    state: dict[str, Any],
    tracer: TraceRecorder,
    otel: OtelTracer,
    started: float,
    interrupted: bool,
) -> None:
    answer = state.get("answer")
    notes = list(getattr(answer, "guardrail_notes", []) or [])
    faith = next((n.split("=", 1)[1] for n in notes if n.startswith("faithfulness=")), None)
    ground = next((n.split("=", 1)[1] for n in notes if n.startswith("groundedness=")), None)
    RUN_STORE.record(
        RunCard(
            run_id=tracer.run_id,
            session_id=session_id,
            question=question,
            started_at=now_iso(),
            finished_at=now_iso(),
            latency_ms=int((time.perf_counter() - started) * 1000),
            interrupted=interrupted,
            hitl_status=getattr(answer, "hitl_status", None),
            patterns=list(getattr(answer, "patterns_used", []) or []),
            agents=[a.value if hasattr(a, "value") else str(a) for a in (getattr(answer, "agents_invoked", []) or [])],
            sql_count=len(getattr(answer, "sql_used", []) or []),
            confidence=float(getattr(answer, "confidence", 0) or 0),
            faithfulness=float(faith) if faith else None,
            groundedness=float(ground) if ground else None,
            otel_trace_id=otel.trace_id,
            summary=(getattr(answer, "summary", "") or "")[:240],
        )
    )


def _initial_state(
    question: str,
    *,
    session_id: str,
    granted_scopes: set[str] | None,
    force_hitl: bool,
    history: list[dict[str, str]] | None,
) -> dict[str, Any]:
    return {
        "question": question,
        "session_id": session_id,
        "history": history or [],
        "tool_results": [],
        "sql_used": [],
        "citations": [],
        "intermediate": [],
        "handoffs": [],
        "skills_used": [],
        "force_hitl": force_hitl,
        "granted_scopes": sorted(granted_scopes or ANALYST_SCOPES),
    }


async def run_agent(
    question: str,
    *,
    session_id: str = "default",
    granted_scopes: set[str] | None = None,
    force_hitl: bool = False,
    history: list[dict[str, str]] | None = None,
) -> tuple[Any, TraceRecorder, OtelTracer]:
    compiled, tracer = build_graph()
    otel = OtelTracer()
    started = time.perf_counter()
    tracer.emit("run.start", question=question, session_id=session_id)
    with otel.span("loyaltydesk.run", session_id=session_id, question=question[:160]):
        state = await compiled.ainvoke(
            _initial_state(
                question,
                session_id=session_id,
                granted_scopes=granted_scopes,
                force_hitl=force_hitl,
                history=history,
            ),
            config=_thread_config(session_id),
        )
    interrupted = bool(state.get("__interrupt__"))
    state = _pending_hitl_patch(state)
    tracer.emit("run.end", ok=state.get("answer") is not None, interrupted=interrupted)
    tracer.persist()
    otel.persist()
    _record_run(
        question=question,
        session_id=session_id,
        state=state,
        tracer=tracer,
        otel=otel,
        started=started,
        interrupted=interrupted,
    )
    return state, tracer, otel


async def stream_agent(
    question: str,
    *,
    session_id: str = "default",
    granted_scopes: set[str] | None = None,
    force_hitl: bool = False,
    history: list[dict[str, str]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield live LangGraph node updates, then a final answer payload."""
    compiled, tracer = build_graph()
    otel = OtelTracer()
    started = time.perf_counter()
    config = _thread_config(session_id)
    tracer.emit("run.start", question=question, session_id=session_id)
    yield {
        "event": "route",
        "agents": [r.value for r in plan_route(question, history)],
        "skills": skills_for_question(question),
    }

    with otel.span("loyaltydesk.run", session_id=session_id, question=question[:160]):
        async for update in compiled.astream(
            _initial_state(
                question,
                session_id=session_id,
                granted_scopes=granted_scopes,
                force_hitl=force_hitl,
                history=history,
            ),
            config=config,
            stream_mode="updates",
        ):
            for node_name, payload in update.items():
                data = payload or {}
                if node_name == "supervisor":
                    yield {
                        "event": "handoff",
                        "from": "supervisor",
                        "to": [
                            r.value if hasattr(r, "value") else r
                            for r in (data.get("route") or [])
                        ],
                        "skills": data.get("skills_used") or [],
                    }
                elif node_name in {"sql_analyst", "knowledge", "loyalty_logic"}:
                    yield {"event": "agent", "agent": node_name, "status": "running"}
                    tools = [
                        t.get("name")
                        for t in (data.get("tool_results") or [])
                        if isinstance(t, dict)
                    ]
                    if tools:
                        yield {"event": "tools", "agent": node_name, "tools": tools}
                    yield {"event": "agent", "agent": node_name, "status": "done"}
                elif node_name == "synthesize":
                    yield {"event": "synthesize", "status": "done"}
                elif node_name == "reflect":
                    yield {
                        "event": "reflection",
                        "status": "done",
                        "notes": (data.get("reflection") or {}).get("notes") or [],
                    }
                elif node_name == "hitl_gate":
                    yield {"event": "hitl", "status": (data.get("hitl") or {}).get("status", "done")}

        snap = await compiled.aget_state(config)
        state = dict(snap.values)
        if snap.interrupts:
            state["__interrupt__"] = list(snap.interrupts)
            yield {"event": "hitl", "status": "pending"}

    state = _pending_hitl_patch(state)
    interrupted = bool(state.get("__interrupt__"))
    tracer.emit("run.end", ok=state.get("answer") is not None, interrupted=interrupted)
    tracer.persist()
    otel.persist()
    _record_run(
        question=question,
        session_id=session_id,
        state=state,
        tracer=tracer,
        otel=otel,
        started=started,
        interrupted=interrupted,
    )
    answer = state.get("answer")
    yield {
        "event": "answer",
        "run_id": tracer.run_id,
        "answer": answer.model_dump(mode="json") if answer else None,
        "traces": tracer.as_dicts(),
        "handoffs": state.get("handoffs") or [],
        "reflection": state.get("reflection"),
        "hitl": state.get("hitl"),
        "skills": state.get("skills_used") or skills_for_question(question),
        "interrupted": interrupted,
        "otel_trace_id": otel.trace_id,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


async def resume_agent(
    session_id: str,
    *,
    approve: bool,
    note: str = "",
) -> tuple[Any, TraceRecorder]:
    """Resume a graph paused on interrupt() — same thread_id required."""
    compiled, tracer = build_graph()
    tracer.emit("hitl.resume", session_id=session_id, approve=approve)
    state = await compiled.ainvoke(
        Command(resume={"approve": approve, "note": note}),
        config=_thread_config(session_id),
    )
    tracer.emit("run.end", ok=state.get("answer") is not None, resumed=True)
    tracer.persist()
    return state, tracer


def stream_status(question: str, history: list[dict[str, str]] | None = None) -> Iterator[dict[str, Any]]:
    route = plan_route(question, history)
    yield {"event": "route", "agents": [r.value for r in route], "skills": skills_for_question(question)}
    for role in route:
        yield {"event": "handoff", "from": "supervisor", "to": role.value}
        yield {"event": "agent", "agent": role.value, "status": "running"}
        yield {"event": "agent", "agent": role.value, "status": "done"}
    yield {"event": "synthesize", "status": "running"}
    yield {"event": "reflection", "status": "running"}
    if requires_hitl(question):
        yield {"event": "hitl", "status": "pending"}
