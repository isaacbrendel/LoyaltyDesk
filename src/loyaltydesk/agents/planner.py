"""Routing + answer synthesis.

Uses a real LLM when configured; otherwise a deterministic loyalty-domain planner
so demos, tests, and CI work without provider keys.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from loyaltydesk.models import AgentRole, AnalystAnswer, Citation


def available_provider() -> str:
    explicit = os.getenv("LOYALTYDESK_LLM_PROVIDER", "").strip().lower()
    if explicit in {"openai", "anthropic", "demo"}:
        if explicit == "openai" and not os.getenv("OPENAI_API_KEY"):
            return "demo"
        if explicit == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
            return "demo"
        return explicit
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "demo"


def plan_route(question: str) -> list[AgentRole]:
    q = question.lower()
    roles: list[AgentRole] = []
    if re.search(r"\b(sql|query|how many|top|segment|campaign uplift|region|tier mix)\b", q) or "churn" in q:
        roles.append(AgentRole.SQL_ANALYST)
    if re.search(r"\b(member|m\d{4}|snapshot|points balance)\b", q):
        roles.append(AgentRole.SQL_ANALYST)
    if re.search(r"\b(earn|burn|redeem|policy|rule|handbook|multiplier|expir)\b", q):
        roles.append(AgentRole.LOYALTY_LOGIC)
        roles.append(AgentRole.KNOWLEDGE)
    if re.search(r"\b(what is|explain|knowledge|cortex|playbook)\b", q):
        roles.append(AgentRole.KNOWLEDGE)
    if not roles:
        roles = [AgentRole.SQL_ANALYST, AgentRole.KNOWLEDGE]
    # stable unique order
    seen: list[AgentRole] = []
    for role in roles:
        if role not in seen:
            seen.append(role)
    return seen


def _member_id(question: str) -> str | None:
    match = re.search(r"\bM\d{4}\b", question, re.IGNORECASE)
    return match.group(0).upper() if match else None


def demo_tool_calls(role: AgentRole, question: str) -> list[dict[str, Any]]:
    """Produce tool calls a supervisor/subagent would emit."""
    q = question.lower()
    mid = _member_id(question)

    if role == AgentRole.SQL_ANALYST:
        if mid:
            return [
                {
                    "name": "member_snapshot",
                    "args": {"member_id": mid},
                },
                {
                    "name": "run_sql",
                    "args": {
                        "sql": (
                            "SELECT category, COUNT(*) AS txns, SUM(amount_usd) AS spend, "
                            "SUM(points_earned) AS points "
                            f"FROM transactions WHERE member_id = '{mid}' "
                            "GROUP BY category ORDER BY spend DESC"
                        ),
                        "reason": f"Category mix for member {mid}",
                    },
                },
            ]
        if "churn" in q or "inactive" in q or "win-back" in q or "winback" in q:
            return [
                {
                    "name": "run_sql",
                    "args": {
                        "sql": (
                            "SELECT member_id, tier, points_balance, last_activity, "
                            "date_diff('day', last_activity, current_date) AS days_inactive "
                            "FROM members WHERE date_diff('day', last_activity, current_date) >= 45 "
                            "ORDER BY days_inactive DESC"
                        ),
                        "reason": "Identify medium/high churn-risk members",
                    },
                },
                {
                    "name": "search_knowledge",
                    "args": {"query": "churn win-back campaign", "top_k": 3},
                },
            ]
        if "campaign" in q or "uplift" in q:
            return [
                {
                    "name": "run_sql",
                    "args": {
                        "sql": (
                            "SELECT campaign_id, name, target_tier, uplift_pct, status, channel "
                            "FROM campaigns ORDER BY uplift_pct DESC"
                        ),
                        "reason": "Rank campaigns by measured uplift",
                    },
                }
            ]
        if "tier" in q:
            return [
                {
                    "name": "run_sql",
                    "args": {
                        "sql": (
                            "SELECT tier, COUNT(*) AS members, AVG(points_balance) AS avg_balance, "
                            "AVG(lifetime_points) AS avg_lifetime FROM members GROUP BY tier "
                            "ORDER BY avg_lifetime DESC"
                        ),
                        "reason": "Tier distribution and engagement",
                    },
                }
            ]
        return [
            {
                "name": "run_sql",
                "args": {
                    "sql": (
                        "SELECT region, COUNT(*) AS members, SUM(points_balance) AS points "
                        "FROM members GROUP BY region ORDER BY members DESC"
                    ),
                    "reason": "Regional member footprint",
                },
            }
        ]

    if role == AgentRole.KNOWLEDGE:
        return [{"name": "search_knowledge", "args": {"query": question, "top_k": 4}}]

    if role == AgentRole.LOYALTY_LOGIC:
        topic = "earn burn tiers"
        if "burn" in q or "redeem" in q:
            topic = "burn redemption"
        elif "earn" in q or "multiplier" in q:
            topic = "earn multipliers"
        elif "campaign" in q:
            topic = "campaign win-back"
        return [{"name": "explain_loyalty_rule", "args": {"topic": topic}}]

    return []


def synthesize_answer(
    question: str,
    *,
    route: list[AgentRole],
    tool_results: list[dict[str, Any]],
    sql_used: list[str],
    citations: list[dict[str, Any]],
) -> AnalystAnswer:
    insights: list[str] = []
    actions: list[str] = []
    summary_bits: list[str] = []

    for item in tool_results:
        name = item.get("name")
        result = item.get("result")
        if name == "run_sql" and isinstance(result, dict):
            rows = result.get("rows") or []
            if rows:
                preview = rows[0]
                insights.append(f"SQL returned {result.get('row_count', len(rows))} row(s); e.g. {json.dumps(preview, default=str)}.")
            else:
                insights.append("SQL returned no rows for that slice of program data.")
        elif name == "member_snapshot" and isinstance(result, dict):
            summary_bits.append(
                f"Member {result['member_id']} is {result['tier']} with {result['points_balance']:,} points "
                f"(lifetime {result['lifetime_points']:,}), churn risk {result['churn_risk']}."
            )
            if result["churn_risk"] != "low":
                actions.append(
                    f"Trigger a personalized win-back in preferred categories: "
                    f"{', '.join(result.get('preferred_categories') or ['general'])}."
                )
            else:
                actions.append("Offer an experiential reward aligned to preferred categories to deepen emotional loyalty.")
        elif name == "search_knowledge" and isinstance(result, list):
            for hit in result[:2]:
                insights.append(f"Knowledge: {hit.get('title')} / {hit.get('section')} — {hit.get('content')}")
                content = (hit.get("content") or "").lower()
                if "win-back" in content or "winback" in content or "90+" in content:
                    actions.append(hit.get("content") or "Run a targeted win-back offer for inactive members.")
        elif name == "explain_loyalty_rule" and isinstance(result, dict):
            summary_bits.append(result.get("summary") or "")
            actions.extend(result.get("edge_cases") or [])

    if not summary_bits:
        if insights:
            summary_bits.append(
                f"Analyzed loyalty program data for: {question.strip()} "
                f"using agents {[r.value for r in route]}."
            )
        else:
            summary_bits.append(
                "I queried available loyalty tools but found limited signal. "
                "Try asking about churn, campaigns, tiers, earn/burn rules, or a member id like M1004."
            )

    conf = 0.82 if tool_results else 0.4
    cite_models = [Citation.model_validate(c) for c in citations]
    return AnalystAnswer(
        summary=" ".join(s for s in summary_bits if s).strip(),
        insights=insights[:6],
        recommended_actions=list(dict.fromkeys(actions))[:5],
        sql_used=sql_used,
        citations=cite_models,
        confidence=conf,
        agents_invoked=route,
    )


async def maybe_llm_synthesize(
    question: str,
    *,
    route: list[AgentRole],
    tool_results: list[dict[str, Any]],
    sql_used: list[str],
    citations: list[dict[str, Any]],
) -> AnalystAnswer:
    """Optional LLM polish — falls back to deterministic synthesis."""
    provider = available_provider()
    base = synthesize_answer(
        question,
        route=route,
        tool_results=tool_results,
        sql_used=sql_used,
        citations=citations,
    )
    if provider == "demo":
        return base

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt = (
            "You are LoyaltyDesk, an internal loyalty analyst agent. "
            "Given tool results JSON, rewrite the summary and insights for a human analyst. "
            "Do not invent numbers not present in tools. Return plain text summary only."
        )
        payload = json.dumps(
            {"question": question, "tool_results": tool_results, "draft": base.model_dump()},
            default=str,
        )
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
        else:
            from langchain_anthropic import ChatAnthropic

            llm = ChatAnthropic(
                model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                temperature=0,
            )
        msg = await llm.ainvoke(
            [SystemMessage(content=prompt), HumanMessage(content=payload)]
        )
        text = str(msg.content).strip()
        if len(text) >= 8:
            return base.model_copy(update={"summary": text, "confidence": min(0.92, base.confidence + 0.05)})
    except Exception:
        return base
    return base
