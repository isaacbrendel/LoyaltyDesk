# LoyaltyDesk

**LLM-native loyalty analyst agent platform** — a portfolio project that demonstrates production AI engineering for loyalty / MarTech: LangGraph agents, AgentCore-shaped packaging, Snowflake/Cortex-style retrieval, evals, guardrails, reflection, and human-in-the-loop.

Repo: [isaacbrendel/genesis](https://cursor.com/codebase/isaacbrendel/genesis)

Deep research notes (citations): [`docs/RESEARCH.md`](docs/RESEARCH.md) · Interview script: [`docs/INTERVIEW.md`](docs/INTERVIEW.md)

## What it shows (mapped to the role)

| Job signal | Where it lives |
|---|---|
| Python agent harness, tool-calling, structured outputs | `agents/`, `models.py`, `tools/` |
| LangGraph supervisor + subagents + handoffs | `agents/graph.py` |
| **LangGraph `interrupt()` + checkpointer HITL** (resume via `Command`) | `agents/graph.py` `hitl_gate` / `resume_agent` |
| Reflection + groundedness/faithfulness | `agents/reflect.py`, `evals/metrics.py` |
| AgentCore Runtime / Gateway / Memory / Policy / Observability / Evals | `agentcore/` + `GET /api/agentcore/manifest` |
| Gateway retries, rate limit, circuit breaker, Cedar-shaped policy | `agentcore/gateway.py`, `policy_engine.py` |
| OTEL-shaped spans (CloudWatch GenAI / ADOT compatible) | `observability/otel.py` |
| Snowflake + Cortex Analyst semantic metrics | `snowflake/` + `ask_semantic` |
| Cortex Search-shaped RAG | `search_knowledge` |
| Golden + **adversarial/OWASP** evals in CI | `evals/` + `.github/workflows/ci.yml` |
| OWASP LLM Top 10 control matrix | `security/owasp.py` + `/api/security/owasp` |
| Bedrock adapter seam | `llm/bedrock.py` |
| Docker + FastAPI streaming UI | `web/`, `/api/chat/stream` |

> No AWS account required. DuckDB stands in for Snowflake; the demo LLM planner runs offline. Add `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` for live summarization + LLM-as-judge.

## Quick start

```bash
uv sync --extra dev
uv run loyaltydesk seed
uv run loyaltydesk serve --port 3847
```

Open [http://127.0.0.1:3847](http://127.0.0.1:3847).

```bash
uv run loyaltydesk ask "Which members look like churn risks and what win-back should we try?"
uv run loyaltydesk ask "Approve and deploy campaign C11 Travel Bonus Week to production."
uv run pytest -q
uv run loyaltydesk-eval
curl -s localhost:3847/api/agentcore/manifest | head
```

### Docker

```bash
docker compose up --build
```

## Architecture

```text
Analyst UI / API  →  policy (injection)  →  AgentCore runtime.invoke()
                                              │
                                    LangGraph supervisor (router)
                                              │ handoffs
                 ┌────────────────────────────┼────────────────────────────┐
                 ▼                            ▼                            ▼
           SQL / semantic              Knowledge (RAG)              Loyalty logic
           ask_semantic / SQL          Cortex Search-like           earn/burn rules
                 │                            │                            │
                 └────────────────────────────┼────────────────────────────┘
                                              ▼
                                    Structured AnalystAnswer
                                              ▼
                                         Reflection
                                              ▼
                              HITL gate (mutations / approvals)
                                              ▼
                                   Traces + eval harness (CI)
```

## Sample questions

- Which members look like churn risks and what win-back should we try?
- Explain how tier multipliers affect dining earn rates.
- Give me a loyalty snapshot for member `M1003`.
- Which loyalty campaigns have the highest uplift right now?
- **Approve and deploy campaign C11 Travel Bonus Week to production.** ← triggers HITL

## Optional real LLMs

```bash
cp .env.example .env
# OPENAI_API_KEY=...  or  ANTHROPIC_API_KEY=...
uv sync --extra llm --extra dev
```
