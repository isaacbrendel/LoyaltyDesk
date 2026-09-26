"""Short-term conversation memory for analyst sessions."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock

from loyaltydesk.config import get_settings
from loyaltydesk.models import ChatMessage


@dataclass
class SessionMemory:
    messages: deque[ChatMessage] = field(default_factory=lambda: deque(maxlen=40))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionMemory] = defaultdict(SessionMemory)
        self._lock = Lock()

    def add(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            session = self._sessions[session_id]
            session.messages.append(ChatMessage(role=role, content=content))
            session.updated_at = datetime.now(UTC)

    def history(self, session_id: str) -> list[ChatMessage]:
        with self._lock:
            self._purge_locked()
            return list(self._sessions[session_id].messages)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def _purge_locked(self) -> None:
        ttl = timedelta(minutes=get_settings().session_ttl_minutes)
        cutoff = datetime.now(UTC) - ttl
        stale = [sid for sid, s in self._sessions.items() if s.updated_at < cutoff]
        for sid in stale:
            del self._sessions[sid]


MEMORY = MemoryStore()
