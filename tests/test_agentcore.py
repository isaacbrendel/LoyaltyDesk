import pytest

from loyaltydesk.agentcore.manifest import get_manifest
from loyaltydesk.agentcore.runtime import invoke
from loyaltydesk.data.seed import seed_warehouse
from loyaltydesk.hitl import HITL_STORE
from loyaltydesk.snowflake.semantic_model import ask_semantic, list_metrics


@pytest.fixture(scope="module", autouse=True)
def _warehouse():
    seed_warehouse()


def test_manifest_has_subagents_and_gateway():
    manifest = get_manifest()
    assert manifest["runtime"]["entrypoint"].endswith("invoke")
    assert any(s["id"] == "reflector" for s in manifest["subagents"])
    assert any(t["name"] == "ask_semantic" for t in manifest["gateway"]["tools"])


def test_semantic_model_resolves_churn():
    out = ask_semantic("Show churn risk members")
    assert out["resolved"] is True
    assert out["metric"] == "churn_risk_members"
    assert out["result"]["row_count"] >= 1
    assert list_metrics()


@pytest.mark.asyncio
async def test_runtime_hitl_pending_and_resolve():
    payload = await invoke(
        "Approve and deploy campaign C11 Travel Bonus Week to production.",
        session_id="hitl-test",
    )
    assert payload["answer"]["hitl_status"] == "pending"
    assert "human_in_the_loop" in payload["answer"]["patterns_used"]
    run_id = payload["run_id"]
    rec = HITL_STORE.get(run_id)
    assert rec is not None
    resolved = HITL_STORE.resolve(run_id, approve=True, note="ship it")
    assert resolved.status == "approved"


@pytest.mark.asyncio
async def test_reflection_notes_present():
    payload = await invoke("Which loyalty campaigns have the highest uplift right now?")
    assert payload["answer"]["reflection_notes"]
    assert "reflection" in payload["answer"]["patterns_used"]
    assert payload["answer"]["sql_used"]
