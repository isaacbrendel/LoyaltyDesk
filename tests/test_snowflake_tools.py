from loyaltydesk.data.seed import seed_warehouse
from loyaltydesk.snowflake.client import SnowflakeClient
from loyaltydesk.tools.registry import invoke_tool


def test_seed_and_sql(tmp_path):
    db = tmp_path / "t.duckdb"
    seed_warehouse(db)
    client = SnowflakeClient(db_path=db)
    result = client.run_sql("SELECT COUNT(*) AS n FROM members")
    assert result.row_count == 1
    assert result.rows[0]["n"] == 8


def test_sql_write_blocked(tmp_path):
    db = tmp_path / "t.duckdb"
    seed_warehouse(db)
    client = SnowflakeClient(db_path=db)
    try:
        client.run_sql("DELETE FROM members")
        assert False, "expected PermissionError"
    except PermissionError:
        pass


def test_tool_scope_enforced():
    try:
        invoke_tool("run_sql", {"sql": "SELECT 1 AS n", "reason": "x"}, granted_scopes={"knowledge:read"})
        assert False, "expected PermissionError"
    except PermissionError:
        pass
