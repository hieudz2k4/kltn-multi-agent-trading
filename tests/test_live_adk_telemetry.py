"""Live integration test: Google ADK execution and telemetry tracking with Gemini Flash."""

import os
import time
from pathlib import Path
from typing import Any, Dict
import pytest
from dotenv import load_dotenv

# Load environment configuration from project root .env
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types


def get_live_xauusd_quote(timeframe: str = "M15") -> Dict[str, Any]:
    """Simulate retrieving XAUUSD quote from MT5."""
    print(f"\n[Tool Executed] get_live_xauusd_quote(timeframe='{timeframe}')")
    return {
        "symbol": "XAUUSD",
        "timeframe": timeframe,
        "bid": 2735.50,
        "ask": 2735.80,
        "spread_pips": 3.0,
        "last_candle": {
            "open": 2730.00,
            "high": 2738.20,
            "low": 2729.50,
            "close": 2735.50,
            "pattern": "Bullish Pinbar sweeping old low liquidity at 2729.50",
        },
    }


def test_live_adk_agent_execution_and_telemetry():
    """Verify Gemini invocation via Google ADK and telemetry metrics collection."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        msg = "Skipped: Missing GOOGLE_API_KEY or GEMINI_API_KEY in .env"
        if __name__ == "__main__":
            print(msg)
            return
        pytest.skip(msg)

    # 1. Initialize Agent
    agent = Agent(
        model="gemini-2.5-flash",
        name="smc_market_analyst",
        description="Expert in gold market technical analysis using Smart Money Concepts (SMC).",
        instruction=(
            "You are a technical analysis expert in Smart Money Concepts (SMC). "
            "When asked about XAUUSD, always call the 'get_live_xauusd_quote' tool to fetch live candle data, "
            "then provide a concise 2-sentence summary of market bias and liquidity sweep levels."
        ),
        tools=[get_live_xauusd_quote],
    )

    # 2. Initialize Runner & Session
    runner = InMemoryRunner(agent=agent, app_name="kltn_trading_system")
    session = runner.session_service.create_session_sync(
        app_name=runner.app_name,
        user_id="trader_hieu",
    )

    # 3. Prepare User Message
    user_prompt = "Check the latest XAUUSD M15 candle data and provide market bias."
    message = types.Content(
        parts=[types.Part.from_text(text=user_prompt)],
        role="user",
    )

    # 4. Execute and Process Events
    start_time = time.time()
    events = runner.run(
        user_id="trader_hieu",
        session_id=session.id,
        new_message=message,
    )

    step_count = 0
    final_text_response = ""
    telemetry_metadata = None

    for event in events:
        step_count += 1
        print(f"\n[Event #{step_count}] author='{event.author}'")

        function_calls = event.get_function_calls()
        if function_calls:
            for call in function_calls:
                print(f"  Tool call: {call.name}({call.args})")

        function_responses = event.get_function_responses()
        if function_responses:
            for resp in function_responses:
                print(f"  Tool result: {resp.response}")

        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    final_text_response += part.text

        if event.usage_metadata:
            telemetry_metadata = event.usage_metadata

    elapsed_time = time.time() - start_time

    # 5. Output Response
    print(f"\n[Response]\n{final_text_response.strip()}\n")

    # 6. Verify Telemetry Metadata
    if telemetry_metadata:
        prompt_tokens = getattr(telemetry_metadata, "prompt_token_count", 0) or 0
        candidates_tokens = getattr(telemetry_metadata, "candidates_token_count", 0) or 0
        total_tokens = getattr(telemetry_metadata, "total_token_count", 0) or 0

        print(
            f"[Telemetry] Prompt tokens: {prompt_tokens} | "
            f"Candidate tokens: {candidates_tokens} | "
            f"Total tokens: {total_tokens} | "
            f"Latency: {elapsed_time:.2f}s"
        )
        assert total_tokens > 0, "Total tokens must be greater than 0"
        assert prompt_tokens > 0, "Prompt tokens must be greater than 0"
    else:
        print("[Telemetry] usage_metadata not found.")

    assert len(final_text_response) > 0, "Response text must not be empty"


if __name__ == "__main__":
    test_live_adk_agent_execution_and_telemetry()
