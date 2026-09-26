import pytest

from loyaltydesk.agents.graph import stream_agent
from loyaltydesk.agents.planner import _member_id, plan_route
from loyaltydesk.data.seed import seed_warehouse
from loyaltydesk.memory import MEMORY


@pytest.fixture(scope="module", autouse=True)
def _warehouse():
    seed_warehouse()


def test_history_resolves_member_for_followup():
    history = [
        {"role": "user", "content": "Give me a loyalty snapshot for member M1003"},
        {"role": "assistant", "content": "Member M1003 is Platinum..."},
    ]
    assert _member_id("What are their preferred categories?", history) == "M1003"
    assert "sql_analyst" in [r.value for r in plan_route("What are their preferred categories?", history)]


@pytest.mark.asyncio
async def test_live_stream_emits_nodes_and_answer():
    events = []
    async for ev in stream_agent(
        "Which loyalty campaigns have the highest uplift right now?",
        session_id="stream-test-1",
    ):
        events.append(ev)
    kinds = [e.get("event") for e in events]
    assert "route" in kinds
    assert "answer" in kinds
    answer = next(e for e in events if e["event"] == "answer")
    assert answer["answer"]["sql_used"]
    assert answer["latency_ms"] >= 0
    assert answer.get("otel_trace_id")


@pytest.mark.asyncio
async def test_session_memory_followup_uses_member():
    sid = "memory-follow-1"
    MEMORY.clear(sid)
    MEMORY.add(sid, "user", "Give me a loyalty snapshot for member M1003")
    MEMORY.add(sid, "assistant", "Member M1003 is Platinum with high engagement.")
    history = [{"role": m.role, "content": m.content} for m in MEMORY.history(sid)]
    events = []
    async for ev in stream_agent(
        "What are their preferred categories?",
        session_id=sid,
        history=history,
    ):
        events.append(ev)
    answer = next(e for e in events if e["event"] == "answer")["answer"]
    blob = answer["summary"] + " ".join(answer.get("insights") or [])
    assert "M1003" in blob or "preferred" in blob.lower() or "travel" in blob.lower()
