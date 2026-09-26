# Research notes — production agent platform patterns

Sources consulted 2026-09-26 via primary documentation extracts and advanced search. Implementation in this repo maps each finding to code.

## 1. LangGraph human-in-the-loop

**Sources**
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/deepagents/human-in-the-loop
- https://reference.langchain.com/python/langgraph/types/interrupt

**Patterns we implement**
- Call `interrupt(payload)` inside the HITL node; graph pauses and returns `__interrupt__`.
- Compile with a **checkpointer** (`MemorySaver` / production: Postgres/Sqlite).
- Resume with `Command(resume=decision)` on the **same `thread_id`**.
- Prefer dynamic interrupts for mutation approval over only static `interrupt_before`.

**Anti-patterns**
- HITL without a checkpointer (cannot resume).
- New `thread_id` on resume (restarts the graph).
- Mutating external systems before the interrupt returns approval.

## 2. Amazon Bedrock AgentCore

**Sources**
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html
- https://aws.amazon.com/bedrock/agentcore/faqs
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-guardrails-getting-started.html

**Patterns we implement**
- Package seams: **Runtime / Gateway / Memory / Policy / Observability / Evaluations**.
- Emit **OpenTelemetry-compatible** spans (AgentCore’s native telemetry shape).
- Enforce policy/guardrails at the **gateway** (outside the model’s reasoning loop).
- Deterministic allow/deny for tool calls; probabilistic detectors feed deterministic policy.

**Anti-patterns**
- Soft “please don’t” prompts as the only guardrail.
- Skipping gateway/memory/identity tracing when debugging production agents.

## 3. Snowflake Cortex Analyst / Search

**Sources**
- https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst (extracted)
- Internal stand-in: verified metric SQL only (`semantic_model.py`)

**Patterns we implement**
- Semantic model of **named metrics** with compiled SQL (Analyst pattern).
- Knowledge docs + sparse retrieval as Cortex Search stand-in.
- Read-only SQL governance (SELECT/WITH only).

## 4. Evaluation harnesses

**Patterns (RAGAS / DeepEval / LangSmith-shaped)**
- Golden dataset regression in CI.
- Faithfulness / groundedness scores vs tool evidence.
- LLM-as-judge when keys exist; rubric surrogate offline.
- Adversarial / OWASP-aligned red-team cases.

## 5. LLM security (OWASP LLM Top 10)

**Source**
- https://owasp.org/www-project-top-10-for-large-language-model-applications/

**Controls mapped in-repo** (`security/owasp.py`)
- LLM01 Prompt injection → input guardrails + policy deny
- LLM02 Insecure output → Pydantic contracts + output redaction
- LLM06 Sensitive info disclosure → PII redaction, no email in summaries
- LLM08 Excessive agency → tool scopes + HITL interrupt for mutations
- LLM09 Misinformation → reflection / groundedness gates

## Implementation map

| Finding | Code |
|---|---|
| interrupt + checkpointer HITL | `agents/graph.py`, `agents/runtime_session.py` |
| AgentCore seams | `agentcore/` |
| OTEL-shaped traces | `observability/otel.py` |
| Gateway policy | `agentcore/policy_engine.py`, `agentcore/gateway.py` |
| Semantic metrics | `snowflake/semantic_model.py` |
| Faithfulness + adversarial evals | `evals/metrics.py`, `evals/adversarial.json` |
| OWASP control matrix | `security/owasp.py` |
