"""Persisted run cards for the ops console (latency, patterns, scores)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from loyaltydesk.config import get_settings


@dataclass
class RunCard:
    run_id: str
    session_id: str
    question: str
    started_at: str
    finished_at: str
    latency_ms: int
    interrupted: bool
    hitl_status: str | None
    patterns: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    sql_count: int = 0
    confidence: float = 0.0
    faithfulness: float | None = None
    groundedness: float | None = None
    otel_trace_id: str | None = None
    summary: str = ""


class RunStore:
    def __init__(self) -> None:
        self._lock = Lock()

    def _path(self) -> Path:
        settings = get_settings()
        settings.trace_dir.mkdir(parents=True, exist_ok=True)
        return settings.trace_dir / "runs.jsonl"

    def record(self, card: RunCard) -> None:
        with self._lock:
            with self._path().open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(card)) + "\n")

    def recent(self, limit: int = 25) -> list[dict[str, Any]]:
        path = self._path()
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        out: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        out.reverse()
        return out

    def stats(self) -> dict[str, Any]:
        rows = self.recent(200)
        if not rows:
            return {"runs": 0, "avg_latency_ms": 0, "hitl_rate": 0, "avg_confidence": 0}
        n = len(rows)
        hitl = sum(1 for r in rows if r.get("hitl_status") == "pending" or r.get("interrupted"))
        return {
            "runs": n,
            "avg_latency_ms": int(sum(r.get("latency_ms", 0) for r in rows) / n),
            "hitl_rate": round(hitl / n, 3),
            "avg_confidence": round(sum(float(r.get("confidence") or 0) for r in rows) / n, 3),
        }


RUN_STORE = RunStore()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
