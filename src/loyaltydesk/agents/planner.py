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


def plan_route(question: str, history: list[dict[str, str]] | None = None) -> list[AgentRole]:
    q = question.lower()
    roles: list[AgentRole] = []
    followup = bool(_member_id(question, history)) and re.search(
        r"\b(their|them|that member|preferred|categories|follow.?up|also)\b", q
    )
    if (
        re.search(r"\b(sql|query|how many|top|segment|campaign uplift|region|tier mix)\b", q)
        or "churn" in q
        or followup
    ):
        roles.append(AgentRole.SQL_ANALYST)
    if re.search(r"\b(member|m\d{4}|snapshot|points balance)\b", q) or followup:
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


def _member_id(question: str, history: list[dict[str, str]] | None = None) -> str | None:
    match = re.search(r"\bM\d{4}\b", question, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    if history:
        for msg in reversed(history):
            found = re.search(r"\bM\d{4}\b", msg.get("content", ""), re.IGNORECASE)
            if found:
                return found.group(0).upper()
    return None


def skills_for_question(question: str) -> list[str]:
    q = question.lower()
    skills: list[str] = []
    if any(k in q for k in ("churn", "inactive", "win-back", "winback")):
        skills.append("churn_playbook")
    if any(k in q for k in ("earn", "burn", "redeem", "multiplier", "tier", "policy")):
        skills.append("handbook_rag")
    if any(k in q for k in ("campaign", "uplift", "member", "sql", "how many", "region")) or re.search(
        r"\bm\d{4}\b", q
    ):
        skills.append("program_sql")
    return skills or ["program_sql"]


def demo_tool_calls(
    role: AgentRole,
    question: str,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Produce tool calls a supervisor/subagent would emit."""
    q = question.lower()
    mid = _member_id(question, history)

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
                    "name": "ask_semantic",
                    "args": {"question": question},
                },
                {
                    "name": "search_knowledge",
                    "args": {"query": "churn win-back campaign", "top_k": 3},
                },
            ]
        if "campaign" in q or "uplift" in q:
            return [{"name": "ask_semantic", "args": {"question": question}}]
        if "tier" in q:
            return [{"name": "ask_semantic", "args": {"question": question}}]
        if "region" in q or "semantic" in q or "cortex" in q:
            return [{"name": "ask_semantic", "args": {"question": question}}]
        return [
            {
                "name": "ask_semantic",
                "args": {"question": question},
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
    history: list[dict[str, str]] | None = None,
) -> AnalystAnswer:
    insights: list[str] = []
    actions: list[str] = []
    summary_bits: list[str] = []
    if history:
        prior = [
            m
            for m in history
            if m.get("role") == "user" and m.get("content", "").strip() != question.strip()
        ][-2:]
        if prior:
            insights.append(
                "Using short-term session memory: "
                + " | ".join(m.get("content", "")[:80] for m in prior)
            )

    for item in tool_results:
        if item.get("ok") is False:
            continue
        name = item.get("name")
        result = item.get("result")
        if name == "run_sql" and isinstance(result, dict):
            rows = result.get("rows") or []
            if rows:
                preview = rows[0]
                insights.append(
                    f"SQL returned {result.get('row_count', len(rows))} row(s); "
                    f"e.g. {json.dumps(preview, default=str)}."
                )
            else:
                insights.append("SQL returned no rows for that slice of program data.")
        elif name == "ask_semantic" and isinstance(result, dict):
            if result.get("resolved"):
                nested = result.get("result") or {}
                rows = nested.get("rows") or []
                insights.append(
                    f"Semantic metric `{result.get('metric')}` "
                    f"({result.get('description')}) → {nested.get('row_count', len(rows))} row(s)."
                )
                if rows:
                    insights.append(f"Top row: {json.dumps(rows[0], default=str)}.")
                summary_bits.append(
                    f"Resolved via Cortex Analyst-shaped semantic model metric "
                    f"`{result.get('metric')}` for: {question.strip()}"
                )
            else:
                insights.append(result.get("message") or "Semantic model could not resolve metric.")
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
                actions.append(
                    "Offer an experiential reward aligned to preferred categories "
                    "to deepen emotional loyalty."
                )
        elif name == "search_knowledge" and isinstance(result, list):
            for hit in result[:2]:
                insights.append(
                    f"Knowledge: {hit.get('title')} / {hit.get('section')} — {hit.get('content')}"
                )
                content = (hit.get("content") or "").lower()
                if "win-back" in content or "winback" in content or "90+" in content:
                    actions.append(
                        hit.get("content") or "Run a targeted win-back offer for inactive members."
                    )
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
    history: list[dict[str, str]] | None = None,
) -> AnalystAnswer:
    """Optional LLM polish — falls back to deterministic synthesis."""
    provider = available_provider()
    base = synthesize_answer(
        question,
        route=route,
        tool_results=tool_results,
        sql_used=sql_used,
        citations=citations,
        history=history,
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
