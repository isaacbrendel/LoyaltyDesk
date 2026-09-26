"""Reflection pass — catch weak evidence before returning to the analyst."""

from __future__ import annotations

from typing import Any

from loyaltydesk.models import AnalystAnswer


def reflect_on_answer(
    question: str,
    answer: AnalystAnswer,
    *,
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    issues: list[str] = []
    score = 1.0

    if not tool_results:
        issues.append("No tools were executed — answer may be unsupported.")
        score -= 0.5

    failed = [t for t in tool_results if t.get("error") or t.get("ok") is False]
    if failed:
        issues.append(f"{len(failed)} tool call(s) failed; treat numbers cautiously.")
        score -= 0.15 * len(failed)

    q = question.lower()
    wants_numbers = any(k in q for k in ("how many", "top", "uplift", "churn", "campaign", "tier"))
    if wants_numbers and not answer.sql_used:
        # Semantic tool still counts if present in tool_results
        semantic_ok = any(
            t.get("name") == "ask_semantic" and isinstance(t.get("result"), dict) and t["result"].get("resolved")
            for t in tool_results
        )
        if not semantic_ok:
            issues.append("Quantitative question without SQL/semantic evidence.")
            score -= 0.35

    if answer.confidence < 0.5:
        issues.append("Model confidence is low.")
        score -= 0.1

    if "ignore previous" in answer.summary.lower():
        issues.append("Suspicious instruction-following language in summary.")
        score -= 0.5

    score = max(0.0, min(1.0, score))
    verdict = "pass" if score >= 0.7 and not any("unsupported" in i for i in issues) else "revise"
    notes = issues or ["Evidence coverage looks sufficient for an analyst draft."]
    return {
        "verdict": verdict,
        "score": score,
        "notes": notes,
        "adjusted_confidence": round(min(answer.confidence, score + 0.1), 3),
    }
