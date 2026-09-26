"""Shared Pydantic contracts for agent I/O and tool results."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AgentRole(str, Enum):
    SUPERVISOR = "supervisor"
    SQL_ANALYST = "sql_analyst"
    KNOWLEDGE = "knowledge"
    LOYALTY_LOGIC = "loyalty_logic"


class ToolName(str, Enum):
    RUN_SQL = "run_sql"
    SEARCH_KNOWLEDGE = "search_knowledge"
    EXPLAIN_RULE = "explain_loyalty_rule"
    MEMBER_SNAPSHOT = "member_snapshot"
    ASK_SEMANTIC = "ask_semantic"


class Citation(BaseModel):
    source: str
    snippet: str
    score: float = Field(ge=0.0, le=1.0)


class SqlQueryResult(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool = False
    warehouse: str = "loyalty_program (DuckDB stand-in for Snowflake)"


class KnowledgeHit(BaseModel):
    doc_id: str
    title: str
    section: str
    content: str
    score: float


class LoyaltyRuleExplanation(BaseModel):
    rule_id: str
    name: str
    summary: str
    earn_formula: str
    burn_constraints: list[str]
    edge_cases: list[str]
    citations: list[Citation] = Field(default_factory=list)


class MemberSnapshot(BaseModel):
    member_id: str
    tier: str
    points_balance: int
    lifetime_points: int
    enroll_date: str
    last_activity: str
    churn_risk: str
    preferred_categories: list[str]


class AnalystAnswer(BaseModel):
    """Structured final answer returned to the analyst UI / callers."""

    summary: str = Field(description="One-paragraph answer for the analyst")
    insights: list[str] = Field(default_factory=list, min_length=0)
    recommended_actions: list[str] = Field(default_factory=list)
    sql_used: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    agents_invoked: list[AgentRole] = Field(default_factory=list)
    guarded: bool = False
    guardrail_notes: list[str] = Field(default_factory=list)
    reflection_notes: list[str] = Field(default_factory=list)
    patterns_used: list[str] = Field(default_factory=list)
    hitl_status: str | None = None  # None | pending | approved | rejected

    @field_validator("summary")
    @classmethod
    def non_empty_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 8:
            raise ValueError("summary must be substantive")
        return cleaned


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TraceEvent(BaseModel):
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    span: str
    role: AgentRole | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
