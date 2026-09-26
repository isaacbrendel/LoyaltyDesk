"""Human-in-the-loop store for high-risk loyalty program proposals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any


@dataclass
class HitlRecord:
    run_id: str
    session_id: str
    question: str
    proposal: dict[str, Any]
    status: str = "pending"  # pending | approved | rejected
    reviewer_note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None


class HitlStore:
    def __init__(self) -> None:
        self._items: dict[str, HitlRecord] = {}
        self._lock = Lock()

    def create(
        self,
        *,
        run_id: str,
        session_id: str,
        question: str,
        proposal: dict[str, Any],
    ) -> HitlRecord:
        rec = HitlRecord(
            run_id=run_id,
            session_id=session_id,
            question=question,
            proposal=proposal,
        )
        with self._lock:
            self._items[run_id] = rec
        return rec

    def get(self, run_id: str) -> HitlRecord | None:
        with self._lock:
            return self._items.get(run_id)

    def resolve(self, run_id: str, *, approve: bool, note: str = "") -> HitlRecord:
        with self._lock:
            rec = self._items.get(run_id)
            if not rec:
                raise KeyError(run_id)
            if rec.status != "pending":
                raise ValueError(f"HITL {run_id} already {rec.status}")
            rec.status = "approved" if approve else "rejected"
            rec.reviewer_note = note
            rec.resolved_at = datetime.now(UTC)
            return rec

    def pending(self) -> list[HitlRecord]:
        with self._lock:
            return [r for r in self._items.values() if r.status == "pending"]


HITL_STORE = HitlStore()
