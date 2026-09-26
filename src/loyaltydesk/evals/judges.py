"""Deterministic + optional LLM-as-judge scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class JudgeResult:
    passed: bool
    score: float
    reasons: list[str]


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

    score = max(0.0, min(1.0, score))
    passed = score >= 0.7
    if passed and not reasons:
        reasons.append("heuristic checks passed")
    return JudgeResult(passed=passed, score=score, reasons=reasons)
