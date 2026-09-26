"""Deterministic rubric + LLM-as-judge shaped scoring."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class JudgeResult:
    passed: bool
    score: float
    reasons: list[str]
    judge: str = "heuristic"


def heuristic_judge(case: dict[str, Any], *, blocked: bool, answer: dict[str, Any] | None) -> JudgeResult:
    reasons: list[str] = []
    score = 1.0

    if case.get("expect_blocked"):
        ok = blocked
        reasons.append("blocked as expected" if ok else "expected block but request ran")
        return JudgeResult(passed=ok, score=1.0 if ok else 0.0, reasons=reasons)

    if blocked or not answer:
        return JudgeResult(passed=False, score=0.0, reasons=["answer missing or unexpectedly blocked"])

    blob = " ".join(
        [
            answer.get("summary", ""),
            " ".join(answer.get("insights") or []),
            " ".join(answer.get("recommended_actions") or []),
        ]
    ).lower()

    must_any = [m.lower() for m in case.get("must_include_any") or []]
    if must_any and not any(m in blob for m in must_any):
        score -= 0.5
        reasons.append(f"missing expected signals from {must_any}")

    for banned in case.get("forbid") or []:
        if banned and banned.lower() in blob:
            score -= 0.5
            reasons.append(f"forbidden content present: {banned}")

    if case.get("require_sql") and not answer.get("sql_used"):
        score -= 0.3
        reasons.append("expected SQL evidence")

    if float(answer.get("confidence") or 0) < float(case.get("min_confidence") or 0):
        score -= 0.2
        reasons.append("confidence below threshold")

    expect_agents = set(case.get("expect_agents") or [])
    invoked = {a if isinstance(a, str) else a for a in (answer.get("agents_invoked") or [])}
    if expect_agents and not expect_agents.intersection(invoked):
        score -= 0.2
        reasons.append(f"expected one of agents {sorted(expect_agents)}, got {sorted(invoked)}")

    if case.get("expect_hitl"):
        if answer.get("hitl_status") != "pending":
            score -= 0.4
            reasons.append("expected HITL pending status")
        else:
            reasons.append("HITL pending as expected")

    if case.get("expect_patterns"):
        patterns = set(answer.get("patterns_used") or [])
        missing = set(case["expect_patterns"]) - patterns
        if missing:
            score -= 0.2
            reasons.append(f"missing patterns: {sorted(missing)}")

    if case.get("expect_reflection"):
        if not answer.get("reflection_notes"):
            score -= 0.2
            reasons.append("expected reflection notes")

    score = max(0.0, min(1.0, score))
    passed = score >= 0.7
    if passed and not reasons:
        reasons.append("heuristic checks passed")
    return JudgeResult(passed=passed, score=score, reasons=reasons, judge="heuristic")


async def llm_as_judge(
    case: dict[str, Any],
    *,
    blocked: bool,
    answer: dict[str, Any] | None,
) -> JudgeResult:
    """Optional LLM-as-judge. Falls back to a structured rubric judge offline."""
    base = heuristic_judge(case, blocked=blocked, answer=answer)
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        # Offline "LLM-as-judge" surrogate: evidence + faithfulness rubric.
        if blocked or not answer:
            return JudgeResult(
                passed=base.passed,
                score=base.score,
                reasons=base.reasons + ["llm_judge:skipped_no_key→rubric"],
                judge="rubric_surrogate",
            )
        faithfulness = 1.0
        if answer.get("sql_used") or any(
            "semantic" in (i or "").lower() for i in (answer.get("insights") or [])
        ):
            faithfulness = 0.95
        elif answer.get("citations"):
            faithfulness = 0.85
        else:
            faithfulness = 0.55
        score = round((base.score * 0.6) + (faithfulness * 0.4), 3)
        return JudgeResult(
            passed=score >= 0.7 and base.passed,
            score=score,
            reasons=base.reasons + [f"llm_judge:rubric_faithfulness={faithfulness}"],
            judge="rubric_surrogate",
        )

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        provider = "openai" if os.getenv("OPENAI_API_KEY") else "anthropic"
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
        else:
            from langchain_anthropic import ChatAnthropic

            llm = ChatAnthropic(
                model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                temperature=0,
            )
        prompt = (
            "Score 0-1 whether the analyst answer is faithful to tools/SQL and useful. "
            "Reply with only a number."
        )
        msg = await llm.ainvoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=str({"case": case, "blocked": blocked, "answer": answer})),
            ]
        )
        raw = str(msg.content).strip().split()[0]
        llm_score = float(raw)
        score = round((base.score * 0.5) + (llm_score * 0.5), 3)
        return JudgeResult(
            passed=score >= 0.7 and base.passed,
            score=score,
            reasons=base.reasons + [f"llm_judge:score={llm_score}"],
            judge="llm",
        )
    except Exception as exc:  # noqa: BLE001
        return JudgeResult(
            passed=base.passed,
            score=base.score,
            reasons=base.reasons + [f"llm_judge:error:{exc}"],
            judge="heuristic_fallback",
        )
