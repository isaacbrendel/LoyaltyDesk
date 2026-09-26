"""Snowflake-shaped data access over DuckDB.

In production this module would wrap Snowflake SQL + Cortex Search / Analyst.
Here DuckDB provides a faithful local stand-in with the same contracts.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb

from loyaltydesk.config import get_settings
from loyaltydesk.data.seed import seed_warehouse, warehouse_path
from loyaltydesk.models import KnowledgeHit, SqlQueryResult

_FORBIDDEN = re.compile(
    r"\b(drop|delete|update|insert|alter|attach|copy|pragma|call)\b",
    re.IGNORECASE,
)


class SnowflakeClient:
    """Read-only program-data client with Cortex-like knowledge search."""

    def __init__(self, db_path: Path | None = None, max_rows: int | None = None) -> None:
        settings = get_settings()
        self.db_path = db_path or warehouse_path()
        self.max_rows = max_rows or settings.max_tool_rows
        if not self.db_path.exists():
            seed_warehouse(self.db_path)

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path), read_only=True)

    def run_sql(self, sql: str) -> SqlQueryResult:
        cleaned = sql.strip().rstrip(";")
        if _FORBIDDEN.search(cleaned):
            raise PermissionError("Only read-only SELECT queries are permitted against program data.")
        if not cleaned.lower().startswith("select") and not cleaned.lower().startswith("with"):
            raise PermissionError("SQL must be a SELECT / WITH query.")

        limited = cleaned
        if "limit" not in cleaned.lower():
            limited = f"{cleaned} LIMIT {self.max_rows + 1}"

        con = self._connect()
        try:
            relation = con.execute(limited)
            columns = [d[0] for d in relation.description]
            raw_rows = relation.fetchall()
        finally:
            con.close()

        truncated = len(raw_rows) > self.max_rows
        rows = [dict(zip(columns, row, strict=True)) for row in raw_rows[: self.max_rows]]
        # Normalize non-JSON-native types
        for row in rows:
            for key, value in list(row.items()):
                if hasattr(value, "isoformat"):
                    row[key] = value.isoformat()
        return SqlQueryResult(
            sql=cleaned,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
        )

    def search_knowledge(self, query: str, top_k: int = 4) -> list[KnowledgeHit]:
        """Sparse keyword search standing in for Snowflake Cortex Search."""
        tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2]
        con = self._connect()
        try:
            docs = con.execute(
                "SELECT doc_id, title, section, content, tags FROM knowledge_docs"
            ).fetchall()
        finally:
            con.close()

        scored: list[KnowledgeHit] = []
        for doc_id, title, section, content, tags in docs:
            hay = f"{title} {section} {content} {tags}".lower()
            if not tokens:
                score = 0.1
            else:
                hits = sum(1 for t in tokens if t in hay)
                score = hits / len(tokens)
            if score > 0:
                scored.append(
                    KnowledgeHit(
                        doc_id=doc_id,
                        title=title,
                        section=section,
                        content=content,
                        score=round(min(score, 1.0), 3),
                    )
                )
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    def member_row(self, member_id: str) -> dict[str, Any] | None:
        con = self._connect()
        try:
            row = con.execute(
                """
                SELECT member_id, tier, points_balance, lifetime_points,
                       enroll_date, last_activity, preferred_categories, email
                FROM members WHERE member_id = ?
                """,
                [member_id],
            ).fetchone()
        finally:
            con.close()
        if not row:
            return None
        keys = [
            "member_id",
            "tier",
            "points_balance",
            "lifetime_points",
            "enroll_date",
            "last_activity",
            "preferred_categories",
            "email",
        ]
        data = dict(zip(keys, row, strict=True))
        for key in ("enroll_date", "last_activity"):
            if hasattr(data[key], "isoformat"):
                data[key] = data[key].isoformat()
        return data


@lru_cache(maxsize=1)
def get_client() -> SnowflakeClient:
    return SnowflakeClient()
