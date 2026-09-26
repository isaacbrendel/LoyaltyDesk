"""Evaluation harness with golden dataset + regression exit codes for CI."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from loyaltydesk.agents.graph import run_agent
from loyaltydesk.data.seed import seed_warehouse
from loyaltydesk.evals.judges import heuristic_judge
from loyaltydesk.guardrails.pipeline import apply_input_guardrails

GOLDEN = Path(__file__).with_name("golden.json")


async def run_case(case: dict) -> dict:
    guard = apply_input_guardrails(case["question"])
    if not guard.allowed:
        judge = heuristic_judge(case, blocked=True, answer=None)
        return {
            "id": case["id"],
            "blocked": True,
            "passed": judge.passed,
            "score": judge.score,
            "reasons": judge.reasons,
        }

    state, tracer = await run_agent(guard.text, session_id=f"eval-{case['id']}")
    answer = state["answer"].model_dump(mode="json")
    judge = heuristic_judge(case, blocked=False, answer=answer)
    return {
        "id": case["id"],
        "blocked": False,
        "passed": judge.passed,
        "score": judge.score,
        "reasons": judge.reasons,
        "run_id": tracer.run_id,
        "confidence": answer.get("confidence"),
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
