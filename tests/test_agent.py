import pytest

from loyaltydesk.agents.graph import run_agent
from loyaltydesk.data.seed import seed_warehouse


@pytest.fixture(scope="module", autouse=True)
def _warehouse():
    seed_warehouse()


@pytest.mark.asyncio
async def test_churn_question_uses_sql():
    state, tracer, otel = await run_agent(
        "Which members look like churn risks and what win-back should we try?",
        session_id="test-churn",
    )
    answer = state["answer"]
    assert answer is not None
    assert answer.sql_used
    assert answer.confidence >= 0.5
    assert tracer.events
    assert otel.spans


@pytest.mark.asyncio
async def test_member_snapshot_no_email_leak():
    state, _, _ = await run_agent(
        "Give me a loyalty snapshot for member M1003",
        session_id="test-member",
    )
    blob = state["answer"].summary + " ".join(state["answer"].insights)
    assert "M1003" in blob
    assert "@" not in blob
