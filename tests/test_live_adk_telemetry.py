"""Live test: Google ADK execution và telemetry tracking (Gemini 3.8 Flash)."""

import os
import time
from pathlib import Path
from typing import Any, Dict
import pytest
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types


def get_live_xauusd_quote(timeframe: str = "M15") -> Dict[str, Any]:
    """Giả lập lấy quote XAUUSD từ MT5."""
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
            "pattern": "Bullish Pinbar quét thanh khoản đáy cũ tại 2729.50",
        },
    }


def test_live_adk_agent_execution_and_telemetry():
    """Kiểm tra gọi Gemini qua ADK và thu thập telemetry."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        msg = "Bỏ qua: Thiếu GOOGLE_API_KEY hoặc GEMINI_API_KEY trong .env"
        if __name__ == "__main__":
            print(msg)
            return
        pytest.skip(msg)

    # 1. Khởi tạo Agent
    agent = Agent(
        model="gemini-2.5-flash",
        name="smc_market_analyst",
        description="Chuyên gia phân tích thị trường vàng theo cấu trúc SMC.",
        instruction=(
            "Bạn là chuyên gia phân tích kỹ thuật theo Smart Money Concepts (SMC). "
            "Khi người dùng hỏi về XAUUSD, hãy luôn gọi tool 'get_live_xauusd_quote' để lấy dữ liệu nến thực tế, "
            "sau đó nhận định ngắn gọn về xu hướng và điểm quét thanh khoản trong đúng 2 câu."
        ),
        tools=[get_live_xauusd_quote],
    )

    # 2. Tạo Runner & Session
    runner = InMemoryRunner(agent=agent, app_name="kltn_trading_system")
    session = runner.session_service.create_session_sync(
        app_name=runner.app_name,
        user_id="trader_hieu",
    )

    # 3. Chuẩn bị prompt
    user_prompt = "Hãy kiểm tra dữ liệu nến XAUUSD M15 gần nhất và đưa ra nhận định xu hướng cho tôi."
    message = types.Content(
        parts=[types.Part.from_text(text=user_prompt)],
        role="user",
    )

    # 4. Chạy và theo dõi events
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

    # 5. Kết quả phản hồi
    print(f"\n[Response]\n{final_text_response.strip()}\n")

    # 6. Kiểm tra Telemetry
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
        assert total_tokens > 0, "Tổng số token phải lớn hơn 0"
        assert prompt_tokens > 0, "Số prompt token phải lớn hơn 0"
    else:
        print("[Telemetry] Không tìm thấy usage_metadata.")

    assert len(final_text_response) > 0, "Phản hồi không được để trống"


if __name__ == "__main__":
    test_live_adk_agent_execution_and_telemetry()
