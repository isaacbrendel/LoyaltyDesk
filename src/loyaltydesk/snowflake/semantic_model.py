"""Cortex Analyst-shaped semantic model over loyalty program metrics.

Analysts (and agents) ask in business language; we compile to verified SQL
against the warehouse. This is the local stand-in for Snowflake Cortex Analyst.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loyaltydesk.snowflake.client import get_client


@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    sql: str
    dimensions: tuple[str, ...]


METRICS: dict[str, Metric] = {
    "members_by_tier": Metric(
        name="members_by_tier",
        description="Member counts and average balances by tier",
        sql=(
            "SELECT tier, COUNT(*) AS members, "
            "AVG(points_balance) AS avg_balance, "
            "AVG(lifetime_points) AS avg_lifetime "
            "FROM members GROUP BY tier ORDER BY avg_lifetime DESC"
        ),
        dimensions=("tier",),
    ),
    "churn_risk_members": Metric(
        name="churn_risk_members",
        description="Members inactive 45+ days with inactivity window",
        sql=(
            "SELECT member_id, tier, points_balance, last_activity, "
            "date_diff('day', last_activity, current_date) AS days_inactive "
            "FROM members WHERE date_diff('day', last_activity, current_date) >= 45 "
            "ORDER BY days_inactive DESC"
        ),
        dimensions=("tier", "days_inactive"),
    ),
    "campaign_uplift": Metric(
        name="campaign_uplift",
        description="Campaigns ranked by measured uplift_pct",
        sql=(
            "SELECT campaign_id, name, target_tier, uplift_pct, status, channel "
            "FROM campaigns ORDER BY uplift_pct DESC"
        ),
        dimensions=("target_tier", "channel", "status"),
    ),
    "regional_footprint": Metric(
        name="regional_footprint",
        description="Members and points by region",
        sql=(
            "SELECT region, COUNT(*) AS members, SUM(points_balance) AS points "
            "FROM members GROUP BY region ORDER BY members DESC"
        ),
        dimensions=("region",),
    ),
    "category_spend": Metric(
        name="category_spend",
        description="Spend and points by transaction category",
        sql=(
            "SELECT category, COUNT(*) AS txns, SUM(amount_usd) AS spend, "
            "SUM(points_earned) AS points FROM transactions "
            "GROUP BY category ORDER BY spend DESC"
        ),
        dimensions=("category",),
    ),
}


def list_metrics() -> list[dict[str, Any]]:
    return [
        {
            "name": m.name,
            "description": m.description,
            "dimensions": list(m.dimensions),
        }
        for m in METRICS.values()
    ]


def resolve_metric(question: str) -> Metric | None:
    q = question.lower()
    if "churn" in q or "inactive" in q or "win-back" in q or "winback" in q:
        return METRICS["churn_risk_members"]
    if "campaign" in q or "uplift" in q:
        return METRICS["campaign_uplift"]
    if "tier" in q:
        return METRICS["members_by_tier"]
    if "region" in q:
        return METRICS["regional_footprint"]
    if "category" in q or "spend" in q:
        return METRICS["category_spend"]
    return None


def ask_semantic(question: str) -> dict[str, Any]:
    metric = resolve_metric(question)
    if metric is None:
        return {
            "resolved": False,
            "message": (
                "No verified metric matched. Available: "
                + ", ".join(sorted(METRICS))
            ),
            "metrics": list_metrics(),
        }
    result = get_client().run_sql(metric.sql)
    return {
        "resolved": True,
        "metric": metric.name,
        "description": metric.description,
        "compiled_sql": metric.sql,
        "result": result.model_dump(mode="json"),
        "semantic_model": "loyalty_program_v1",
    }
