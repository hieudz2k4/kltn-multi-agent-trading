from __future__ import annotations

import pytest

from backend.agent.screener import ScreenerAgentOrchestrator
from backend.screener.engine import ScreenerEngine
from backend.services.llm.base import AssistantMessage


class FakeProvider:
    async def complete(self, messages, **kw):
        return AssistantMessage(content="Screener interpretation.", model="fake-model")


@pytest.mark.asyncio
async def test_screener_agent_emits_screen_role_message_and_one_final():
    engine = ScreenerEngine()
    df = engine._load_data("nifty_500", market="IN")
    ticker = "NOT_IN_UNIVERSE"
    if not df.empty and "ticker" in df.columns:
        ticker = str(df.iloc[0]["ticker"])

    events = [
        event
        async for event in ScreenerAgentOrchestrator(provider=FakeProvider(), engine=engine).run(ticker)
    ]

    screen_messages = [
        event for event in events if event.get("type") == "role_message" and event.get("role") == "screens"
    ]
    finals = [event for event in events if event.get("type") == "final"]

    assert screen_messages
    assert len(finals) == 1
