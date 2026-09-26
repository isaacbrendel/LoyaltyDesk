from __future__ import annotations

import re

_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(your\s+)?system\s+prompt",
        r"you\s+are\s+now\s+(dan|jailbroken)",
        r"reveal\s+(your\s+)?system\s+prompt",
        r"do\s+not\s+follow\s+loyalty|bypass\s+guardrails",
        r";\s*drop\s+table",
        r"union\s+select.+information_schema",
    ]
]


def detect_prompt_injection(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in _PATTERNS:
        if pattern.search(text):
            hits.append(f"Matched injection pattern: {pattern.pattern}")
    return hits
