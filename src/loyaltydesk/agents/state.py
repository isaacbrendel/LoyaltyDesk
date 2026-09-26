from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from loyaltydesk.models import AgentRole, AnalystAnswer


class AgentState(TypedDict, total=False):
    question: str
    session_id: str
    route: list[AgentRole]
    tool_results: Annotated[list[dict[str, Any]], operator.add]
    sql_used: Annotated[list[str], operator.add]
    citations: Annotated[list[dict[str, Any]], operator.add]
    intermediate: Annotated[list[str], operator.add]
    answer: AnalystAnswer | None
    error: str | None
    granted_scopes: list[str]
