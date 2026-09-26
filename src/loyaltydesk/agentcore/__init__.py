"""AgentCore-shaped packaging seams for LoyaltyDesk."""

from loyaltydesk.agentcore.manifest import get_manifest

__all__ = ["get_manifest", "invoke"]


def __getattr__(name: str):
    if name == "invoke":
        from loyaltydesk.agentcore.runtime import invoke

        return invoke
    raise AttributeError(name)
