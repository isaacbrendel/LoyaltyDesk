"""Amazon Bedrock model adapter seam (optional).

In production this would call Bedrock Runtime / AgentCore-hosted models.
Locally we keep a typed interface so the rest of the harness stays provider-agnostic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol


class ChatModel(Protocol):
    async def acomplete(self, system: str, user: str) -> str: ...


@dataclass
class BedrockConfig:
    region: str = "us-east-1"
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"


class DemoBedrockAdapter:
    """Deterministic stand-in proving the Bedrock seam without AWS credentials."""

    def __init__(self, config: BedrockConfig | None = None) -> None:
        self.config = config or BedrockConfig()

    async def acomplete(self, system: str, user: str) -> str:
        return (
            f"[bedrock-demo:{self.config.model_id}] "
            "Summarize only from provided tool evidence; refuse unsupported claims."
        )


def get_bedrock_adapter() -> ChatModel | None:
    if os.getenv("LOYALTYDESK_LLM_PROVIDER", "").lower() != "bedrock":
        return None
    # Real boto3 client would be constructed here when AWS creds exist.
    return DemoBedrockAdapter()


def bedrock_health() -> dict[str, Any]:
    return {
        "provider": "bedrock",
        "configured": os.getenv("LOYALTYDESK_LLM_PROVIDER", "").lower() == "bedrock",
        "adapter": "demo" if get_bedrock_adapter() else None,
        "note": "Swap DemoBedrockAdapter for boto3 bedrock-runtime in AWS accounts.",
    }
