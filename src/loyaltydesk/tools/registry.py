"""Agent-callable tools with Pydantic contracts and auth scopes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from pydantic import BaseModel, Field

from loyaltydesk.guardrails.tool_scope import assert_tool_allowed
from loyaltydesk.models import (
    Citation,
    KnowledgeHit,
    LoyaltyRuleExplanation,
    MemberSnapshot,
    SqlQueryResult,
    ToolName,
)
from loyaltydesk.snowflake.client import get_client


class RunSqlArgs(BaseModel):
    sql: str = Field(description="Read-only SELECT against loyalty program tables")
    reason: str = Field(description="Why this query answers the analyst question")


class SearchKnowledgeArgs(BaseModel):
    query: str
    top_k: int = Field(default=4, ge=1, le=8)


class ExplainRuleArgs(BaseModel):
    topic: str = Field(description="Earn, burn, tier, campaign, or churn topic")


class MemberSnapshotArgs(BaseModel):
    member_id: str


def _churn_risk(last_activity: str, points_balance: int) -> str:
    last = date.fromisoformat(str(last_activity)[:10])
    days = (date.today() - last).days
    if days >= 90 and points_balance < 2000:
        return "high"
    if days >= 45:
        return "medium"
    return "low"


def run_sql(args: RunSqlArgs) -> SqlQueryResult:
    return get_client().run_sql(args.sql)


def search_knowledge(args: SearchKnowledgeArgs) -> list[KnowledgeHit]:
    return get_client().search_knowledge(args.query, top_k=args.top_k)


def explain_loyalty_rule(args: ExplainRuleArgs) -> LoyaltyRuleExplanation:
    hits = get_client().search_knowledge(args.topic, top_k=3)
    if not hits:
        return LoyaltyRuleExplanation(
            rule_id="UNKNOWN",
            name="No matching rule",
            summary="No handbook section matched that topic. Ask about earn, burn, tiers, or campaigns.",
            earn_formula="n/a",
            burn_constraints=[],
            edge_cases=[],
        )
    primary = hits[0]
    burn_hits = [h for h in hits if "burn" in h.content.lower() or "redemption" in h.content.lower()]
    return LoyaltyRuleExplanation(
        rule_id=primary.doc_id,
        name=f"{primary.title} — {primary.section}",
        summary=primary.content,
        earn_formula=next((h.content for h in hits if "earn" in h.section.lower() or "multiplier" in h.section.lower()), primary.content),
        burn_constraints=[h.content for h in burn_hits] or ["Minimum redemption and inactivity expiry apply; see handbook."],
        edge_cases=[
            "Excluded SKUs cannot earn or burn.",
            "Campaign bonuses stack after tier multipliers.",
        ],
        citations=[
            Citation(source=f"{h.doc_id}:{h.section}", snippet=h.content[:180], score=h.score)
            for h in hits
        ],
    )


def member_snapshot(args: MemberSnapshotArgs) -> MemberSnapshot:
    row = get_client().member_row(args.member_id)
    if not row:
        raise ValueError(f"Unknown member_id: {args.member_id}")
    cats = [c.strip() for c in str(row["preferred_categories"]).split(",") if c.strip()]
    return MemberSnapshot(
        member_id=row["member_id"],
        tier=row["tier"],
        points_balance=int(row["points_balance"]),
        lifetime_points=int(row["lifetime_points"]),
        enroll_date=str(row["enroll_date"]),
        last_activity=str(row["last_activity"]),
        churn_risk=_churn_risk(str(row["last_activity"]), int(row["points_balance"])),
        preferred_categories=cats,
    )


TOOL_IMPLS: dict[ToolName, Callable[[BaseModel], Any]] = {
    ToolName.RUN_SQL: run_sql,
    ToolName.SEARCH_KNOWLEDGE: search_knowledge,
    ToolName.EXPLAIN_RULE: explain_loyalty_rule,
    ToolName.MEMBER_SNAPSHOT: member_snapshot,
}

TOOL_ARGS: dict[ToolName, type[BaseModel]] = {
    ToolName.RUN_SQL: RunSqlArgs,
    ToolName.SEARCH_KNOWLEDGE: SearchKnowledgeArgs,
    ToolName.EXPLAIN_RULE: ExplainRuleArgs,
    ToolName.MEMBER_SNAPSHOT: MemberSnapshotArgs,
}

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": ToolName.RUN_SQL.value,
        "description": "Run a read-only SQL query against Snowflake-backed loyalty program tables.",
        "args_schema": RunSqlArgs.model_json_schema(),
        "scopes": ["sql:read"],
    },
    {
        "name": ToolName.SEARCH_KNOWLEDGE.value,
        "description": "Search loyalty handbook / policy knowledge (Cortex Search stand-in).",
        "args_schema": SearchKnowledgeArgs.model_json_schema(),
        "scopes": ["knowledge:read"],
    },
    {
        "name": ToolName.EXPLAIN_RULE.value,
        "description": "Explain earn/burn/tier loyalty logic with citations.",
        "args_schema": ExplainRuleArgs.model_json_schema(),
        "scopes": ["knowledge:read", "logic:read"],
    },
    {
        "name": ToolName.MEMBER_SNAPSHOT.value,
        "description": "Fetch a member loyalty snapshot without dumping raw PII into the answer.",
        "args_schema": MemberSnapshotArgs.model_json_schema(),
        "scopes": ["member:read"],
    },
]


def build_tool_map() -> dict[str, dict[str, Any]]:
    return {spec["name"]: spec for spec in TOOL_SPECS}


def invoke_tool(
    name: str,
    raw_args: dict[str, Any],
    *,
    granted_scopes: set[str],
) -> Any:
    tool = ToolName(name)
    assert_tool_allowed(tool, granted_scopes)
    args_model = TOOL_ARGS[tool].model_validate(raw_args)
    result = TOOL_IMPLS[tool](args_model)
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, list):
        return [r.model_dump(mode="json") if isinstance(r, BaseModel) else r for r in result]
    return result


def json_safe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value
