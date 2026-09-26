"""OpenTelemetry-shaped span export (AgentCore Observability compatible format).

AgentCore emits OTEL-compatible telemetry for CloudWatch GenAI Observability.
We produce the same conceptual shape locally as JSONL spans.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from loyaltydesk.config import get_settings


@dataclass
class Span:
    trace_id: str
    span_id: str
    name: str
    start_ns: int
    end_ns: int | None = None
    parent_span_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "UNSET"

    def to_otel(self) -> dict[str, Any]:
        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "loyaltydesk"}},
                            {
                                "key": "telemetry.sdk.name",
                                "value": {"stringValue": "loyaltydesk.otel"},
                            },
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "loyaltydesk"},
                            "spans": [
                                {
                                    "traceId": self.trace_id,
                                    "spanId": self.span_id,
                                    "parentSpanId": self.parent_span_id,
                                    "name": self.name,
                                    "kind": 1,
                                    "startTimeUnixNano": str(self.start_ns),
                                    "endTimeUnixNano": str(self.end_ns or self.start_ns),
                                    "attributes": [
                                        {
                                            "key": k,
                                            "value": {"stringValue": str(v)},
                                        }
                                        for k, v in self.attributes.items()
                                    ],
                                    "status": {"code": 1 if self.status == "OK" else 2},
                                }
                            ],
                        }
                    ],
                }
            ]
        }


class OtelTracer:
    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = (trace_id or uuid4().hex).ljust(32, "0")[:32]
        self.spans: list[Span] = []

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Span]:
        current = Span(
            trace_id=self.trace_id,
            span_id=uuid4().hex[:16],
            name=name,
            start_ns=time.time_ns(),
            attributes=attributes,
            parent_span_id=self.spans[-1].span_id if self.spans else None,
        )
        try:
            yield current
            current.status = "OK"
        except Exception as exc:  # noqa: BLE001
            current.status = "ERROR"
            current.attributes["exception.message"] = str(exc)
            raise
        finally:
            current.end_ns = time.time_ns()
            self.spans.append(current)

    def persist(self) -> Path:
        settings = get_settings()
        out = settings.trace_dir / f"otel-{self.trace_id[:12]}.jsonl"
        settings.trace_dir.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for span in self.spans:
                fh.write(json.dumps(span.to_otel()) + "\n")
        return out
