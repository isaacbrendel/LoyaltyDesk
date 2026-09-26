from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from loyaltydesk.models import AgentRole, AnalystAnswer


class AgentState(TypedDict, total=False):
    question: str
    session_id: str
    history: list[dict[str, str]]
    route: list[AgentRole]
    tool_results: Annotated[list[dict[str, Any]], operator.add]
    sql_used: Annotated[list[str], operator.add]
    citations: Annotated[list[dict[str, Any]], operator.add]
    intermediate: Annotated[list[str], operator.add]
    handoffs: Annotated[list[dict[str, Any]], operator.add]
    answer: AnalystAnswer | None
    reflection: dict[str, Any] | None
    hitl: dict[str, Any] | None
    force_hitl: bool
    error: str | None
    granted_scopes: list[str]
    skills_used: list[str]
