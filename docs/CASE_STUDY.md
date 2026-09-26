# LoyaltyDesk — case study for AI Engineer (loyalty / AgentCore)

**Artifact:** production-shaped internal agent platform for loyalty analysts  
**Repo:** [isaacbrendel/genesis](https://cursor.com/codebase/isaacbrendel/genesis)  
**Run:** `uv run loyaltydesk serve --port 3847` → workbench `/` · ops `/ops`

This is not a toy chatbot. It is the kind of system the role describes: an LLM-native way for analysts to work with program data and loyalty logic, with packaging, evals, guardrails, and observability you can defend in an interview.

---

## The problem (loyalty domain)

Loyalty analysts live in Snowflake tables, earn/burn handbooks, and campaign uplift math. They need:

1. Answers with **evidence** (SQL / semantic metrics / citations)
2. Safe automation (no silent program mutations)
3. Reliability you can **measure in CI**

LoyaltyDesk is that workbench.

---

## What I built (maps 1:1 to the JD)

| JD ask | Concrete proof |
|---|---|
| Python agent harness (LangGraph) | Supervisor → SQL / knowledge / loyalty-logic → synthesize → reflect → HITL |
| Tool calling + Pydantic structured outputs | `tools/registry.py`, `AnalystAnswer` |
| Retries + streaming + memory | Gateway retries; **live** LangGraph `astream` to UI; session memory for follow-ups |
| AgentCore packaging | Runtime / Gateway / Memory / Policy / Observability / Evaluations in `agentcore/manifest.py` |
| Snowflake + knowledge retrieval | DuckDB warehouse + Cortex Analyst-shaped `ask_semantic` + handbook search |
| Evals + golden + LLM-as-judge + CI | `loyaltydesk-eval` (golden + adversarial) in GitHub Actions |
| Guardrails | Injection deny, PII redaction, scopes, reflection, faithfulness/groundedness |
| Multi-agent patterns | Router, handoff, reflection, **LangGraph `interrupt()` HITL** |
| Observability | OTEL-shaped spans + ops console latency/HITL/confidence |

Open `/ops` for the live proof map and recent run metrics.

---

## Beyond what is asked

Most portfolio agents stop at “chat + tools.” This goes further:

1. **Real HITL** — `interrupt()` + checkpointer + `Command(resume)` (LangGraph docs pattern), not a fake boolean.
2. **Gateway policy outside the model** — AgentCore-aligned; deterministic deny for mutating SQL / missing scopes; rate limit + circuit breaker.
3. **OTEL export shape** — same conceptual telemetry AgentCore sends to CloudWatch GenAI Observability.
4. **Adversarial eval suite** — OWASP-aligned red-team cases fail the build if broken.
5. **Ops console** — hiring managers can see latency, HITL rate, and the JD→demo map without reading every file.
6. **Research citations** — `docs/RESEARCH.md` shows I read the primary sources, not blog vibes.
7. **Interview script** — `docs/INTERVIEW.md` so the walkthrough is crisp under pressure.

---

## Demo script (8 minutes)

1. **Churn** starter → live node stream, semantic SQL, win-back actions, reflection notes.  
2. Follow-up: “What are their preferred categories for the riskiest member?” → session memory resolves member context.  
3. **HITL** starter → graph interrupts; Approve & resume via `Command`.  
4. Injection attempt → blocked at guardrail/gateway.  
5. Open **`/ops`** → proof map + run latency.  
6. Terminal: `uv run pytest -q` and `uv run loyaltydesk-eval` → green.

---

## Design opinion (say this out loud)

> Agents earn their keep on multi-step analyst workflows. Fixed SQL and batch jobs should stay tools and jobs. Contracts, evidence, gateway policy, and eval gates are how you ship something that holds up for real teams — which is the bar this role sets.

---

## Honest next steps (builds trust)

- Swap DuckDB client for Snowflake + Cortex Search/Analyst in-account.  
- Wire `DemoBedrockAdapter` to Bedrock Runtime / AgentCore deploy.  
- Persist checkpointer to Postgres for multi-instance HITL.  
- Export OTEL to ADOT → CloudWatch in AWS.

Those are integration steps on top of a harness that already matches the job’s architecture.
