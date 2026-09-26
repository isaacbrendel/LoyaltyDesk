# LoyaltyDesk — interview talking points

Use this when walking a hiring manager through the repo for an AI Engineer /
loyalty platform role (AgentCore, LangGraph, Snowflake, evals, guardrails).

## Elevator pitch (30 seconds)

> LoyaltyDesk is a production-shaped **internal agent platform for loyalty analysts**.
> A LangGraph supervisor routes to SQL, knowledge, and loyalty-logic subagents,
> tools hit a Snowflake-shaped warehouse with a Cortex Analyst semantic model,
> outputs are Pydantic-structured, guardrailed, reflected, and eval-gated in CI.
> High-risk program changes pause for human-in-the-loop approval — the same seams
> you'd package into Amazon AgentCore Runtime.

## Architecture walk (5 minutes)

1. **Open** `src/loyaltydesk/agentcore/manifest.py` — runtime, gateway, memory, policy, skills, subagents.
2. **Open** `src/loyaltydesk/agents/graph.py` — supervisor → subagents → synthesize → **reflection** → **HITL gate**.
3. **Open** `src/loyaltydesk/tools/registry.py` — JSON-schema tool contracts + scopes.
4. **Open** `src/loyaltydesk/snowflake/semantic_model.py` — verified metrics (Cortex Analyst pattern).
5. **Open** `src/loyaltydesk/evals/` — golden set + LLM-as-judge/rubric + CI failure on regression.
6. **Demo** the UI: churn question, then “Approve and deploy campaign…” to show HITL.

## Design opinions worth saying out loud

- **Agents are expensive.** Use them for multi-step analyst workflows; not for fixed SQL templates or batch ETL.
- **Contracts over vibes.** Every tool has Pydantic args; final answers are structured `AnalystAnswer`.
- **Evidence or don't ship.** Reflection downgrades confidence when SQL/semantic evidence is missing.
- **Fail closed.** Injection blocked at the edge; write SQL denied; scopes enforced in the gateway; mutations need a human.
- **Eval is a product feature.** Golden cases run in CI — reliability is owned, not hoped for.

## Mapping to common job requirements

| Requirement | Demo cue |
|---|---|
| LangGraph / agent harness | Graph nodes + handoff events in traces |
| Tool calling + structured outputs | `/api/tools` + `AnalystAnswer` |
| Snowflake / Cortex | DuckDB warehouse + `ask_semantic` |
| AgentCore packaging | `/api/agentcore/manifest` |
| Multi-agent patterns | router, handoff, reflection, HITL |
| Evals + CI | `uv run loyaltydesk-eval` |
| Guardrails / PII | Injection case + email redaction tests |
| Observability | `data/traces/*.jsonl` spans |
| Loyalty domain | Earn/burn handbook + churn playbook |

## Live commands

```bash
uv run loyaltydesk seed
uv run loyaltydesk ask "Which members look like churn risks and what win-back should we try?"
uv run loyaltydesk ask "Approve and deploy campaign C11 Travel Bonus Week to production."
uv run pytest -q          # prove unit suite
uv run loyaltydesk-eval   # golden + adversarial (must be 0 failed)
curl -s localhost:3847/api/agentcore/manifest | jq '.subagents,.observability,.evaluations'
curl -s localhost:3847/api/security/owasp | jq '.mitigated,.total'
```

## Research-backed talking points

See [`RESEARCH.md`](RESEARCH.md). Call out specifically:

1. HITL uses LangGraph **`interrupt()` + MemorySaver + `Command(resume=...)`** — not a fake flag.
2. AgentCore Observability is **OTEL-compatible**; we emit the same span shape locally.
3. Policy/guardrails run at the **gateway**, outside the model's ability to reason around them.
4. Evals include **adversarial/OWASP** cases and faithfulness/groundedness metrics in CI.

## Honest gaps (builds trust)

- Demo LLM planner is deterministic without API keys — swap in Bedrock/OpenAI for production summarization.
- DuckDB stands in for Snowflake; swap `SnowflakeClient` for a real connector + Cortex Search/Analyst.
- AgentCore manifest is the packaging seam — wire the same `invoke()` into a real AgentCore Runtime deploy next.
