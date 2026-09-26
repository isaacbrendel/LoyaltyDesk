import pytest

from loyaltydesk.llm.bedrock import DemoBedrockAdapter, bedrock_health
from loyaltydesk.agentcore.runtime import invoke, resume


@pytest.mark.asyncio
async def test_bedrock_demo_adapter():
    adapter = DemoBedrockAdapter()
    text = await adapter.acomplete("sys", "user")
    assert "bedrock-demo" in text
    health = bedrock_health()
    assert "provider" in health


@pytest.mark.asyncio
async def test_hitl_reject_path():
    session = "hitl-reject-thread"
    payload = await invoke(
        "Approve and change earn rate for Gold tier in production.",
        session_id=session,
    )
    assert payload["interrupted"] is True
    resumed = await resume(session_id=session, approve=False, note="too risky", run_id=payload["run_id"])
    assert resumed["answer"]["hitl_status"] == "rejected"
    assert "rejected" in resumed["answer"]["summary"].lower()
