from __future__ import annotations

from loyaltydesk.models import ToolName

TOOL_SCOPES: dict[ToolName, set[str]] = {
    ToolName.RUN_SQL: {"sql:read"},
    ToolName.SEARCH_KNOWLEDGE: {"knowledge:read"},
    ToolName.EXPLAIN_RULE: {"knowledge:read", "logic:read"},
    ToolName.MEMBER_SNAPSHOT: {"member:read"},
}

ANALYST_SCOPES = {"sql:read", "knowledge:read", "logic:read", "member:read"}
READONLY_SCOPES = {"knowledge:read", "logic:read"}


def assert_tool_allowed(tool: ToolName, granted: set[str]) -> None:
    required = TOOL_SCOPES[tool]
    if not required.issubset(granted):
        missing = ", ".join(sorted(required - granted))
        raise PermissionError(f"Tool {tool.value} denied; missing scopes: {missing}")
