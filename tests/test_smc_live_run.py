"""Live end-to-end dry run test of SMC Multi-Agent Pipeline with InMemoryRunner."""

import os
from pathlib import Path
from dotenv import load_dotenv

import sys
env_path = Path(__file__).resolve().parent.parent / ".env"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(dotenv_path=env_path)

from google.adk.runners import InMemoryRunner
from google.genai import types

from src.agents.smc.smc_orchestrator import create_smc_orchestrator


def test_smc_pipeline_dry_run():
    """Chạy thử nghiệm 1 chu kỳ SMC pipeline qua InMemoryRunner với mock tools."""
    os.environ["MT5_MOCK"] = "true"
    os.environ["TV_MOCK"] = "true"

    orchestrator = create_smc_orchestrator()
    runner = InMemoryRunner(agent=orchestrator, app_name="kltn_smc_dry_run")
    session = runner.session_service.create_session_sync(
        app_name=runner.app_name,
        user_id="trader_test",
        state={"symbol": "XAUUSD"},
    )

    prompt = (
        "Thực hiện quy trình phân tích SMC cho symbol 'XAUUSD': "
        "Chuyển giao cho các sub-agents theo thứ tự: htf_bias_agent -> structure_agent -> poi_agent -> "
        "sizer_agent -> risk_gatekeeper. Báo cáo kết quả cuối cùng."
    )
    message = types.Content(
        parts=[types.Part.from_text(text=prompt)],
        role="user",
    )

    events = runner.run(
        user_id="trader_test",
        session_id=session.id,
        new_message=message,
    )

    events_list = []
    for evt in events:
        events_list.append(evt)
        print(f"[{evt.author}] {getattr(evt.content, 'parts', '')}")
    assert len(events_list) > 0, "Pipeline phải trả về ít nhất một event"
    print(f"\n[SMC Dry Run] Hoàn tất chu kỳ với {len(events_list)} events.")


if __name__ == "__main__":
    test_smc_pipeline_dry_run()
