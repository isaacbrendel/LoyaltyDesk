"""Seed a local DuckDB warehouse that stands in for Snowflake program data."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from loyaltydesk.config import get_settings

SCHEMA = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")

MEMBERS = [
    ("M1001", "alex.rivera@example.com", "Alex", "Rivera", "Gold", 18420, 92000, "2021-03-12", "2026-09-18", "Midwest", "travel,dining"),
    ("M1002", "jordan.lee@example.com", "Jordan", "Lee", "Silver", 6200, 28000, "2022-07-01", "2026-08-02", "West", "grocery,fuel"),
    ("M1003", "sam.okafor@example.com", "Sam", "Okafor", "Platinum", 45200, 210000, "2019-11-20", "2026-09-20", "Northeast", "travel,apparel"),
    ("M1004", "casey.nguyen@example.com", "Casey", "Nguyen", "Bronze", 890, 4200, "2024-01-15", "2026-05-11", "South", "grocery"),
    ("M1005", "riley.chen@example.com", "Riley", "Chen", "Gold", 12100, 76000, "2020-09-08", "2026-09-10", "West", "dining,entertainment"),
    ("M1006", "morgan.patel@example.com", "Morgan", "Patel", "Silver", 4100, 19500, "2023-04-22", "2026-07-30", "Midwest", "fuel,grocery"),
    ("M1007", "avery.brooks@example.com", "Avery", "Brooks", "Platinum", 51050, 245000, "2018-06-03", "2026-09-21", "Northeast", "travel,dining"),
    ("M1008", "quinn.diaz@example.com", "Quinn", "Diaz", "Bronze", 1450, 6100, "2024-06-01", "2026-04-02", "South", "apparel"),
]

TRANSACTIONS = [
    ("T9001", "M1001", "2026-09-18", "pos", "dining", 86.40, 172, 0),
    ("T9002", "M1001", "2026-09-10", "online", "travel", 420.00, 1260, 0),
    ("T9003", "M1002", "2026-08-02", "pos", "grocery", 64.10, 64, 0),
    ("T9004", "M1003", "2026-09-20", "app", "travel", 980.00, 3920, 5000),
    ("T9005", "M1003", "2026-09-05", "pos", "apparel", 210.00, 840, 0),
    ("T9006", "M1004", "2026-05-11", "pos", "grocery", 42.00, 42, 0),
    ("T9007", "M1005", "2026-09-10", "online", "entertainment", 55.00, 110, 0),
    ("T9008", "M1005", "2026-08-28", "pos", "dining", 120.00, 240, 2000),
    ("T9009", "M1006", "2026-07-30", "pos", "fuel", 48.00, 48, 0),
    ("T9010", "M1007", "2026-09-21", "online", "travel", 1500.00, 6000, 0),
    ("T9011", "M1007", "2026-09-01", "app", "dining", 95.00, 380, 2500),
    ("T9012", "M1008", "2026-04-02", "online", "apparel", 78.00, 78, 0),
    ("T9013", "M1001", "2026-07-15", "pos", "dining", 54.00, 108, 0),
    ("T9014", "M1002", "2026-06-20", "pos", "fuel", 39.00, 39, 0),
    ("T9015", "M1004", "2026-03-01", "pos", "grocery", 51.00, 51, 0),
]

CAMPAIGNS = [
    ("C10", "Fall Double Points Dining", "2026-09-01", "2026-10-15", "email", "Gold", 12.4, "active"),
    ("C11", "Travel Bonus Week", "2026-09-10", "2026-09-24", "push", "Platinum", 18.1, "active"),
    ("C12", "Win-back Bronze", "2026-04-01", "2026-05-31", "email", "Bronze", 6.2, "completed"),
    ("C13", "Grocery Everyday", "2026-06-01", "2026-12-31", "app", "Silver", 4.8, "active"),
]

TIERS = [
    ("Bronze", 0, 1.0, "Base earn; birthday bonus"),
    ("Silver", 15000, 1.25, "Free shipping; bonus event access"),
    ("Gold", 50000, 1.5, "Priority support; lounge partners"),
    ("Platinum", 150000, 2.0, "Concierge; experiential rewards"),
]

KNOWLEDGE = [
    (
        "KD01",
        "Earn Rules Handbook",
        "Base earn",
        "Members earn 1 point per $1 spent in grocery and fuel, 2 points per $1 in dining, "
        "and 3–4 points per $1 in travel depending on tier multiplier. Points post within 48 hours.",
        "earn,points,tiers",
    ),
    (
        "KD02",
        "Earn Rules Handbook",
        "Tier multipliers",
        "Bronze 1.0x, Silver 1.25x, Gold 1.5x, Platinum 2.0x apply to base category earn before campaign bonuses.",
        "earn,tiers,multipliers",
    ),
    (
        "KD03",
        "Burn & Redemption Policy",
        "Redemption floors",
        "Minimum redemption is 2,000 points. Travel redemptions require 5,000 points. "
        "Points expire after 24 months of inactivity.",
        "burn,redemption,expiry",
    ),
    (
        "KD04",
        "Burn & Redemption Policy",
        "Restricted SKUs",
        "Gift cards, lottery, and regulated categories are excluded from earn and burn. "
        "Agents must refuse to invent redemption rates for excluded categories.",
        "burn,exclusions,compliance",
    ),
    (
        "KD05",
        "Campaign Playbook",
        "Win-back",
        "Win-back campaigns target members with no activity in 90+ days. Recommended offer: "
        "2x points for 14 days plus a 1,000 point bonus on first return purchase over $25.",
        "campaigns,churn,winback",
    ),
    (
        "KD06",
        "Campaign Playbook",
        "Uplift measurement",
        "Campaign uplift is measured as incremental spend vs a holdout cohort over the campaign window. "
        "Analysts should cite campaign_id and uplift_pct from the campaigns table.",
        "campaigns,measurement,sql",
    ),
    (
        "KD07",
        "Churn Signals",
        "Risk tiers",
        "High churn risk: no activity 90+ days and balance under 2,000. Medium: 45–89 days inactive. "
        "Low: activity within 45 days. Prefer personalized category bonuses over blanket discounts.",
        "churn,risk,personalization",
    ),
    (
        "KD08",
        "Semantic Model Notes",
        "Member metrics",
        "Canonical metrics: points_balance, lifetime_points, tier, last_activity, region. "
        "Join transactions.member_id to members.member_id. Do not expose email in analyst summaries unless requested with a business reason.",
        "semantic,pii,sql",
    ),
]


def warehouse_path(data_dir: Path | None = None) -> Path:
    settings = get_settings()
    root = data_dir or settings.data_dir
    root.mkdir(parents=True, exist_ok=True)
    return root / "loyalty_program.duckdb"


def seed_warehouse(db_path: Path | None = None) -> Path:
    path = db_path or warehouse_path()
    if path.exists():
        path.unlink()
    con = duckdb.connect(str(path))
    try:
        con.execute(SCHEMA)
        con.executemany(
            "INSERT INTO members VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            MEMBERS,
        )
        con.executemany(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            TRANSACTIONS,
        )
        con.executemany(
            "INSERT INTO campaigns VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            CAMPAIGNS,
        )
        con.executemany("INSERT INTO tiers VALUES (?, ?, ?, ?)", TIERS)
        con.executemany(
            "INSERT INTO knowledge_docs VALUES (?, ?, ?, ?, ?)",
            KNOWLEDGE,
        )
    finally:
        con.close()
    meta = path.with_suffix(".meta.json")
    meta.write_text(
        json.dumps({"tables": ["members", "transactions", "campaigns", "tiers", "knowledge_docs"]}),
        encoding="utf-8",
    )
    return path


def main() -> None:
    path = seed_warehouse()
    print(f"Seeded warehouse at {path}")


if __name__ == "__main__":
    main()
