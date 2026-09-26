# LoyaltyDesk

**LLM-native loyalty analyst agent platform** — a portfolio project that demonstrates the production AI engineering skills in a loyalty / MarTech setting: LangGraph agents, tool contracts, Snowflake-shaped retrieval, evaluation harnesses, guardrails, and observable runs.

LoyaltyDesk is the kind of internal agent surface an AI engineer would ship for analysts who live in program data and complex earn/burn logic.

## What it shows (mapped to the role)

| Job signal | Where it lives in this repo |
|---|---|
| Python agent harness with tool-calling + structured outputs | `src/loyaltydesk/agents/`, `src/loyaltydesk/models.py`, `src/loyaltydesk/tools/` |
| LangGraph supervisor + subagents | `src/loyaltydesk/agents/graph.py` (supervisor → SQL / knowledge / loyalty-logic → synthesize) |
| Pydantic / JSON-schema tool contracts | `src/loyaltydesk/tools/registry.py` |
| Snowflake program data + SQL tools | DuckDB stand-in in `src/loyaltydesk/snowflake/client.py` + seed data |
| Snowflake-backed knowledge retrieval (Cortex-shaped) | `search_knowledge` over `knowledge_docs` |
| Packaging context, tools, skills, subagents | Graph nodes + scoped tool registry; FastAPI runtime in `src/loyaltydesk/api/` |
| Streaming + memory | SSE `/api/chat/stream`, session memory in `src/loyaltydesk/memory.py` |
| Evals: golden set, judges, CI regression | `src/loyaltydesk/evals/` + `.github/workflows/ci.yml` |
| Guardrails: auth scopes, I/O validation, PII, injection, hallucination caution | `src/loyaltydesk/guardrails/` |
| Observability / traces | JSONL traces in `src/loyaltydesk/observability/` → `data/traces/` |
| Docker + modern API | `Dockerfile`, `docker-compose.yml`, FastAPI |
| Loyalty domain fluency | Earn/burn handbook, tiers, campaigns, churn playbook in seed data |

> No AWS account required. The warehouse is a **DuckDB stand-in for Snowflake**; the LLM defaults to a **deterministic demo planner** so the full tool loop runs offline. Point `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` at a real model when you want LLM-polished summaries.

## Quick start

```bash
# requires Python 3.12+ and uv (https://github.com/astral-sh/uv)
uv sync --extra dev
uv run loyaltydesk seed
uv run loyaltydesk serve --port 3847
```

Open [http://127.0.0.1:3847](http://127.0.0.1:3847).

### CLI ask

```bash
uv run loyaltydesk ask "Which members look like churn risks and what win-back should we try?"
```

### Tests + golden evals

```bash
uv run pytest -q
uv run loyaltydesk-eval
```

### Docker

```bash
docker compose up --build
```

## Architecture

```text
Analyst UI / API
      │
      ▼
 Input guardrails (injection) ──► LangGraph supervisor
                                      │
                 ┌────────────────────┼────────────────────┐
                 ▼                    ▼                    ▼
           SQL analyst         Knowledge agent      Loyalty-logic agent
           (run_sql,           (Cortex-like         (explain_loyalty_rule)
            member_snapshot)    search)
                 │                    │                    │
                 └────────────────────┼────────────────────┘
                                      ▼
                         Structured AnalystAnswer (Pydantic)
                                      ▼
                         Output guardrails (PII / evidence)
                                      ▼
                              Trace JSONL + UI
```

### Sample questions

- Which members look like churn risks and what win-back should we try?
- Explain how tier multipliers affect dining earn rates.
- Give me a loyalty snapshot for member `M1003`.
- Which loyalty campaigns have the highest uplift right now?

## Optional real LLMs

```bash
cp .env.example .env
# OPENAI_API_KEY=...   or   ANTHROPIC_API_KEY=...
# LOYALTYDESK_LLM_PROVIDER=openai
uv sync --extra llm --extra dev
```

## Project layout

```text
src/loyaltydesk/
  agents/           LangGraph supervisor + subagents
  tools/            Scoped tools with Pydantic args
  snowflake/        Warehouse client (DuckDB → Snowflake-shaped)
  guardrails/       Injection, PII, tool auth, output checks
  evals/            Golden dataset + CI harness
  observability/    Run traces
  api/              FastAPI + SSE streaming
web/                Analyst workbench UI
tests/              Unit + agent + eval regression
```

## Design choices (intentional)

- **Agents only where they earn their keep** — routing is explicit; SQL and handbook retrieval are tools with contracts, not free-form model inventiveness.
- **Evidence over vibes** — answers carry SQL used, citations, confidence, and agent lineage.
- **Fail closed on safety** — write SQL blocked; tool scopes enforced; injection attempts short-circuit before the graph runs.
- **Eval in CI** — if the golden suite regresses, the build fails.

Built as a concrete, runnable slice of an internal loyalty agent platform — not a slide deck.
