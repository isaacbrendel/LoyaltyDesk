from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from loyaltydesk import __version__
from loyaltydesk.agentcore.manifest import get_manifest
from loyaltydesk.agentcore.runtime import invoke
from loyaltydesk.agents.graph import stream_status
from loyaltydesk.agents.planner import available_provider
from loyaltydesk.api.schemas import ChatRequest, ChatResponse, HealthResponse, HitlResolveRequest
from loyaltydesk.config import get_settings
from loyaltydesk.data.seed import seed_warehouse, warehouse_path
from loyaltydesk.guardrails.pipeline import apply_input_guardrails
from loyaltydesk.hitl import HITL_STORE
from loyaltydesk.memory import MEMORY
from loyaltydesk.models import AnalystAnswer
from loyaltydesk.snowflake.semantic_model import list_metrics

WEB_DIR = Path(__file__).resolve().parents[3] / "web"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.trace_dir.mkdir(parents=True, exist_ok=True)
    if not warehouse_path().exists():
        seed_warehouse()
    yield


app = FastAPI(
    title="LoyaltyDesk",
    description="LLM-native loyalty analyst agent platform",
    version=__version__,
    lifespan=lifespan,
)

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>LoyaltyDesk API</h1><p>UI bundle missing.</p>")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        warehouse_ready=warehouse_path().exists(),
        llm_provider=available_provider(),
    )


@app.get("/api/tools")
def list_tools() -> dict:
    from loyaltydesk.tools.registry import TOOL_SPECS

    return {"tools": TOOL_SPECS}


@app.get("/api/agentcore/manifest")
def agentcore_manifest() -> dict:
    return get_manifest()


@app.get("/api/semantic/metrics")
def semantic_metrics() -> dict:
    return {"semantic_model": "loyalty_program_v1", "metrics": list_metrics()}


@app.get("/api/hitl/pending")
def hitl_pending() -> dict:
    items = [
        {
            "run_id": r.run_id,
            "session_id": r.session_id,
            "question": r.question,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in HITL_STORE.pending()
    ]
    return {"pending": items}


@app.post("/api/hitl/{run_id}/resolve")
def hitl_resolve(run_id: str, body: HitlResolveRequest) -> dict:
    try:
        rec = HITL_STORE.resolve(run_id, approve=body.approve, note=body.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown HITL run") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "run_id": rec.run_id,
        "status": rec.status,
        "reviewer_note": rec.reviewer_note,
        "resolved_at": rec.resolved_at.isoformat() if rec.resolved_at else None,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    guard = apply_input_guardrails(body.message)
    if not guard.allowed:
        blocked = AnalystAnswer(
            summary="I can't run that request. It looks like prompt-injection or a policy bypass attempt.",
            insights=guard.notes,
            recommended_actions=["Ask a loyalty analytics or program-rules question instead."],
            confidence=1.0,
            guarded=True,
            guardrail_notes=guard.notes,
        )
        return ChatResponse(
            answer=blocked,
            session_id=body.session_id,
            run_id="blocked",
            blocked=True,
            block_reason=guard.notes,
        )

    MEMORY.add(body.session_id, "user", guard.text)
    payload = await invoke(guard.text, session_id=body.session_id)
    answer_data = payload.get("answer")
    if answer_data is None:
        raise HTTPException(status_code=500, detail="Agent failed")
    answer = AnalystAnswer.model_validate(answer_data)
    MEMORY.add(body.session_id, "assistant", answer.summary)
    return ChatResponse(
        answer=answer,
        session_id=body.session_id,
        run_id=payload.get("run_id") or "unknown",
        traces=payload.get("traces") or [],
        handoffs=payload.get("handoffs") or [],
        reflection=payload.get("reflection"),
        hitl=payload.get("hitl"),
    )


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest) -> StreamingResponse:
    guard = apply_input_guardrails(body.message)
    if not guard.allowed:
        async def blocked():
            payload = {"event": "blocked", "notes": guard.notes}
            yield f"data: {json.dumps(payload)}\n\n"
            yield 'data: {"event": "done"}\n\n'

        return StreamingResponse(blocked(), media_type="text/event-stream")

    async def events():
        for status in stream_status(guard.text):
            yield f"data: {json.dumps(status)}\n\n"
        payload = await invoke(guard.text, session_id=body.session_id)
        answer = payload.get("answer")
        out = {
            "event": "answer",
            "run_id": payload.get("run_id"),
            "answer": answer,
            "traces": payload.get("traces") or [],
            "handoffs": payload.get("handoffs") or [],
            "reflection": payload.get("reflection"),
            "hitl": payload.get("hitl"),
        }
        yield f"data: {json.dumps(out)}\n\n"
        yield 'data: {"event": "done"}\n\n'

    return StreamingResponse(events(), media_type="text/event-stream")
