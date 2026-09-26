from __future__ import annotations

import argparse
import asyncio
import json

import uvicorn

from loyaltydesk.agents.graph import run_agent
from loyaltydesk.config import get_settings
from loyaltydesk.data.seed import seed_warehouse
from loyaltydesk.guardrails.pipeline import apply_input_guardrails


def main() -> None:
    parser = argparse.ArgumentParser(description="LoyaltyDesk CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("seed", help="Seed the local Snowflake stand-in warehouse")

    ask = sub.add_parser("ask", help="Ask the loyalty analyst agent")
    ask.add_argument("question", nargs="+")

    serve = sub.add_parser("serve", help="Run the FastAPI demo UI / API")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    args = parser.parse_args()
    settings = get_settings()

    if args.cmd == "seed":
        path = seed_warehouse()
        print(path)
        return

    if args.cmd == "ask":
        question = " ".join(args.question)
        guard = apply_input_guardrails(question)
        if not guard.allowed:
            print(json.dumps({"blocked": True, "notes": guard.notes}, indent=2))
            return

        async def _run():
            state, tracer = await run_agent(guard.text)
            print(
                json.dumps(
                    {
                        "run_id": tracer.run_id,
                        "answer": state["answer"].model_dump(mode="json"),
                        "traces": tracer.as_dicts(),
                    },
                    indent=2,
                )
            )

        asyncio.run(_run())
        return

    if args.cmd == "serve":
        uvicorn.run(
            "loyaltydesk.api.app:app",
            host=args.host or settings.host,
            port=args.port or settings.port,
            reload=False,
        )


if __name__ == "__main__":
    main()
