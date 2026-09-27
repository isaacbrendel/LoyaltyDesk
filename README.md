# LoyaltyDesk

**v0.4** — LLM-native loyalty analyst agent platform. Production-shaped harness for loyalty / MarTech: LangGraph agents, AgentCore packaging, Snowflake/Cortex-style retrieval, live streaming UI, evals, guardrails, reflection, and human-in-the-loop.

Repo: [isaacbrendel/LoyaltyDesk](https://github.com/isaacbrendel/LoyaltyDesk)

**Docs:** [`docs/CASE_STUDY.md`](docs/CASE_STUDY.md) · [`docs/INTERVIEW.md`](docs/INTERVIEW.md) · [`docs/RESEARCH.md`](docs/RESEARCH.md)

## What it includes

| Capability | Where it lives |
|---|---|
| Python agent harness, tool-calling, structured outputs | `src/loyaltydesk/agents/`, `models.py`, `tools/` |
| LangGraph supervisor + subagents + handoffs | `agents/graph.py` |
| **Live node streaming** (`astream` → SSE) | `agents/graph.py`, `POST /api/chat/stream` |
| Session memory for multi-turn follow-ups | `memory.py` |
| **LangGraph `interrupt()` + checkpointer HITL** (resume via `Command`) | `agents/graph.py` `hitl_gate` / `resume_agent` |
| Reflection + groundedness/faithfulness | `agents/reflect.py`, `evals/metrics.py` |
| AgentCore Runtime / Gateway / Memory / Policy / Observability / Evals | `agentcore/` + `GET /api/agentcore/manifest` |
| Gateway retries, rate limit, circuit breaker, Cedar-shaped policy | `agentcore/gateway.py`, `policy_engine.py` |
| OTEL-shaped spans (CloudWatch GenAI / ADOT compatible) | `observability/otel.py` |
| Ops console — run latency, confidence, pending approvals | `/ops`, `observability/run_store.py` |
| Snowflake + Cortex Analyst semantic metrics | `snowflake/` + `ask_semantic` |
| Cortex Search-shaped RAG | `search_knowledge` |
| Golden + **adversarial/OWASP** evals in CI | `evals/` + `.github/workflows/ci.yml` |
| OWASP LLM Top 10 control matrix | `security/owasp.py` + `/api/security/owasp` |
| Bedrock adapter seam | `llm/bedrock.py` |
| FastAPI workbench + Docker | `web/`, `Dockerfile` |

Paths above are under `src/loyaltydesk/` unless noted.

> No AWS account required. DuckDB stands in for Snowflake; the demo LLM planner runs offline. Add `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` for live summarization + LLM-as-judge.

## Quick start

```bash
uv sync --extra dev
uv run loyaltydesk seed
uv run loyaltydesk serve --port 3847
```

Open [http://127.0.0.1:3847](http://127.0.0.1:3847) for the analyst workbench, or [http://127.0.0.1:3847/ops](http://127.0.0.1:3847/ops) for the ops console.

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
Analyst UI / API  →  policy (injection)  →  AgentCore runtime.invoke() / invoke_stream()
                                              │
                                    LangGraph supervisor (router) + session memory
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
                         Traces + ops run store + eval harness (CI)
```

## Surfaces

| Route / API | Purpose |
|---|---|
| `/` | Analyst workbench — live agent stream, evidence, HITL approve/reject |
| `/ops` | Ops console — run health, pending approvals, recent latency/confidence |
| `POST /api/chat/stream` | SSE stream of LangGraph node updates + final answer |
| `POST /api/chat` | Non-streaming chat |
| `GET /api/agentcore/manifest` | AgentCore-shaped packaging manifest |
| `GET /api/security/owasp` | OWASP LLM Top 10 control matrix |
| `GET /api/hitl/pending` · `POST /api/hitl/{run_id}/resolve` | Approval queue |

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
