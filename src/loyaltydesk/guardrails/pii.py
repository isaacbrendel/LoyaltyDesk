from __future__ import annotations

import re

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def redact_pii(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    out = text
    if EMAIL_RE.search(out):
        out = EMAIL_RE.sub("[REDACTED_EMAIL]", out)
        notes.append("Redacted email addresses from output.")
    if PHONE_RE.search(out):
        out = PHONE_RE.sub("[REDACTED_PHONE]", out)
        notes.append("Redacted phone numbers from output.")
    if SSN_RE.search(out):
        out = SSN_RE.sub("[REDACTED_SSN]", out)
        notes.append("Redacted SSN-like patterns from output.")
    return out, notes
