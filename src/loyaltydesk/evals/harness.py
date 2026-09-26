"""Evaluation harness with golden dataset + LLM-as-judge + CI exit codes."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from loyaltydesk.agentcore.runtime import invoke
from loyaltydesk.data.seed import seed_warehouse
from loyaltydesk.evals.judges import llm_as_judge
from loyaltydesk.guardrails.pipeline import apply_input_guardrails

GOLDEN = Path(__file__).with_name("golden.json")


async def run_case(case: dict) -> dict:
    guard = apply_input_guardrails(case["question"])
    if not guard.allowed:
        judge = await llm_as_judge(case, blocked=True, answer=None)
        return {
            "id": case["id"],
            "blocked": True,
            "passed": judge.passed,
            "score": judge.score,
            "reasons": judge.reasons,
            "judge": judge.judge,
        }

    payload = await invoke(guard.text, session_id=f"eval-{case['id']}")
    answer = payload.get("answer")
    judge = await llm_as_judge(case, blocked=False, answer=answer)
    return {
        "id": case["id"],
        "blocked": False,
        "passed": judge.passed,
        "score": judge.score,
        "reasons": judge.reasons,
        "judge": judge.judge,
        "run_id": payload.get("run_id"),
        "confidence": (answer or {}).get("confidence"),
        "hitl": (answer or {}).get("hitl_status"),
        "patterns": (answer or {}).get("patterns_used"),
    }


async def run_suite() -> dict:
    seed_warehouse()
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    results = [await run_case(case) for case in cases]
    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }


def main() -> None:
    report = asyncio.run(run_suite())
    print(json.dumps(report, indent=2))
    if report["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
