from __future__ import annotations

from pydantic import BaseModel, Field

from loyaltydesk.guardrails.injection import detect_prompt_injection
from loyaltydesk.guardrails.pii import redact_pii
from loyaltydesk.models import AnalystAnswer


class GuardrailResult(BaseModel):
    allowed: bool = True
    text: str
    notes: list[str] = Field(default_factory=list)


def apply_input_guardrails(text: str) -> GuardrailResult:
    notes = detect_prompt_injection(text)
    if notes:
        return GuardrailResult(
            allowed=False,
            text=text,
            notes=notes
            + [
                "Request blocked: prompt-injection / policy-bypass language detected. "
                "Rephrase as a loyalty analytics question."
            ],
        )
    return GuardrailResult(allowed=True, text=text.strip(), notes=[])


def apply_output_guardrails(answer: AnalystAnswer) -> AnalystAnswer:
    summary, notes = redact_pii(answer.summary)
    insights: list[str] = []
    for item in answer.insights:
        cleaned, extra = redact_pii(item)
        insights.append(cleaned)
        notes.extend(extra)
    actions: list[str] = []
    for item in answer.recommended_actions:
        cleaned, extra = redact_pii(item)
        actions.append(cleaned)
        notes.extend(extra)

    # Hallucination mitigation: require evidence for SQL-ish claims
    if answer.sql_used and not answer.insights:
        notes.append("Added caution: SQL was executed but no insights were attached.")
    if answer.confidence < 0.45:
        notes.append("Low confidence — analyst should verify against source tables.")

    return answer.model_copy(
        update={
            "summary": summary,
            "insights": insights,
            "recommended_actions": actions,
            "guarded": bool(notes) or answer.guarded,
            "guardrail_notes": list(dict.fromkeys([*answer.guardrail_notes, *notes])),
        }
    )
