"""Lightweight trace sink (OpenTelemetry / Langfuse / CloudWatch shaped)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from loyaltydesk.config import get_settings
from loyaltydesk.models import AgentRole, TraceEvent


class TraceRecorder:
    def __init__(self, run_id: str | None = None, trace_dir: Path | None = None) -> None:
        settings = get_settings()
        self.run_id = run_id or uuid4().hex[:12]
        self.trace_dir = trace_dir or settings.trace_dir
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.events: list[TraceEvent] = []

    def emit(self, span: str, *, role: AgentRole | None = None, **detail: Any) -> None:
        event = TraceEvent(span=span, role=role, detail=detail)
        self.events.append(event)

    def persist(self) -> Path:
        path = self.trace_dir / f"{self.run_id}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for event in self.events:
                fh.write(event.model_dump_json() + "\n")
        return path

    def as_dicts(self) -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in self.events]
