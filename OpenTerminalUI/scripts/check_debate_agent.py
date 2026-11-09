"""Dev utility: smoke-test the debate agent end-to-end against a live LLM provider.

Runs the DebateOrchestrator for a single symbol and prints each streamed event.
Requires provider credentials (e.g. GEMINI_API_KEY). Run from the repo root:
    python -m scripts.check_debate_agent
"""

import asyncio
from backend.services.llm.factory import get_llm_provider
from backend.agent.debate.orchestrator import DebateOrchestrator
from backend.agent.tools.market_tools import build_default_registry

async def check():
    provider = get_llm_provider(provider="gemini", model="gemini-2.5-flash")
    registry = build_default_registry()
    orch = DebateOrchestrator(provider=provider, registry=registry, analyst_max_steps=2)
    
    print("Testing debate agent...")
    async for event in orch.run("AAPL"):
        print(f"EVENT {event.get('type')}: {str(event)[:200]}")
        if event.get("type") == "error":
            print("==== ERROR EVENT ====")
            print(event)

if __name__ == "__main__":
    asyncio.run(check())
