-- Loyalty program warehouse schema (DuckDB stand-in for Snowflake)

CREATE TABLE IF NOT EXISTS members (
    member_id VARCHAR PRIMARY KEY,
    email VARCHAR,
    first_name VARCHAR,
    last_name VARCHAR,
    tier VARCHAR,
    points_balance INTEGER,
    lifetime_points INTEGER,
    enroll_date DATE,
    last_activity DATE,
    region VARCHAR,
    preferred_categories VARCHAR
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id VARCHAR PRIMARY KEY,
    member_id VARCHAR,
    txn_date DATE,
    channel VARCHAR,
    category VARCHAR,
    amount_usd DOUBLE,
    points_earned INTEGER,
    points_burned INTEGER
);

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id VARCHAR PRIMARY KEY,
    name VARCHAR,
    start_date DATE,
    end_date DATE,
    channel VARCHAR,
    target_tier VARCHAR,
    uplift_pct DOUBLE,
    status VARCHAR
);

CREATE TABLE IF NOT EXISTS tiers (
    tier VARCHAR PRIMARY KEY,
    min_lifetime_points INTEGER,
    earn_multiplier DOUBLE,
    benefits VARCHAR
);

CREATE TABLE IF NOT EXISTS knowledge_docs (
    doc_id VARCHAR PRIMARY KEY,
    title VARCHAR,
    section VARCHAR,
    content VARCHAR,
    tags VARCHAR
);
