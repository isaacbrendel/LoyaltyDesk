"""RAGAS-shaped faithfulness / groundedness metrics (offline-capable)."""

from __future__ import annotations

import re
from typing import Any


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def evidence_blob(tool_results: list[dict[str, Any]], sql_used: list[str]) -> str:
    parts: list[str] = list(sql_used)
    for item in tool_results:
        if item.get("ok") is False:
            continue
        result = item.get("result")
        parts.append(json_dumps(result))
    return " ".join(parts)


def json_dumps(value: Any) -> str:
    import json

    try:
        return json.dumps(value, default=str)
    except TypeError:
        return str(value)


def faithfulness(answer_text: str, evidence: str) -> float:
    """Fraction of answer content tokens supported by evidence tokens."""
    a = _tokens(answer_text)
    e = _tokens(evidence)
    if not a:
        return 0.0
    if not e:
        return 0.2
    overlap = len(a & e)
    # Allow connective words by not requiring 100%
    return round(min(1.0, overlap / max(1, len(a) * 0.35)), 3)


def groundedness(answer: dict[str, Any], tool_results: list[dict[str, Any]]) -> float:
    has_tools = any(t.get("ok") for t in tool_results) if tool_results else False
    has_sql = bool(answer.get("sql_used"))
    has_citations = bool(answer.get("citations"))
    score = 0.2
    if has_tools:
        score += 0.4
    if has_sql:
        score += 0.25
    if has_citations:
        score += 0.15
    return round(min(1.0, score), 3)


def score_answer(
    answer: dict[str, Any],
    *,
    tool_results: list[dict[str, Any]],
) -> dict[str, float]:
    blob = " ".join(
        [
            answer.get("summary", ""),
            " ".join(answer.get("insights") or []),
            " ".join(answer.get("recommended_actions") or []),
        ]
    )
    evidence = evidence_blob(tool_results, answer.get("sql_used") or [])
    return {
        "faithfulness": faithfulness(blob, evidence),
        "groundedness": groundedness(answer, tool_results),
    }
