"""Multi-Model Evaluation Unit Suite for SMC & Risk Agents.

Verifies behavioral alignment across:
- gemini-4-argon
- gemini-3.8-flash
- deepseek-v4.1-flash

Covers both Legacy Baseline agents and New Cognitive Multi-Agent components.
"""

import json
import pytest
from tests.eval.run_agent_eval import (
    SUPPORTED_MODELS,
    evaluate_adversarial_risk,
    evaluate_circuit_breaker,
    evaluate_htf_bias,
    evaluate_macro_sentiment,
    evaluate_poi,
    evaluate_sizer,
    evaluate_smc_strategy,
    evaluate_structure,
)


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_htf_bias_multi_model(model: str):
    """Ensure all models accurately detect liquidity sweep & bullish bias."""
    prompt = "Phân tích cụm nến M15: Nến 1 tạo đáy 2729.50, Nến 2 quét râu về 2728.00 rồi đóng nến tại 2735.00."
    res = evaluate_htf_bias(prompt, {}, model)

    assert res["model"] == model
    assert res["bias"] == "BULLISH"
    assert res["key_level"] == 2728.00
    assert any(t["name"] == "get_live_xauusd_quote" for t in res["tool_calls"])


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_market_structure_multi_model(model: str):
    """Ensure all models identify BOS Bullish and reject CHoCH on higher highs."""
    prompt = "Kiểm tra chuỗi đỉnh/đáy ngắn hạn M15 khi giá tạo đỉnh cao hơn (HH) và đáy cao hơn (HL)."
    res = evaluate_structure(prompt, {}, model)

    assert res["model"] == model
    assert res["structure_type"] == "BOS_BULLISH"
    assert res["entry_direction"] == "BUY"


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_poi_fvg_multi_model(model: str):
    """Ensure all models locate FVG within the Fibonacci Discount zone."""
    prompt = "Dữ liệu nến xuất hiện vùng FVG (Fair Value Gap) trùng khớp với mức thoái lui Fibonacci 0.618 - 0.705 (Discount Zone)."
    res = evaluate_poi(prompt, {}, model)

    assert res["model"] == model
    assert res["poi_type"] == "FVG"
    assert res["entry_zone"]["price_low"] >= 2720.0
    assert res["entry_zone"]["price_high"] <= 2735.0


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_sizer_capital_preservation_multi_model(model: str):
    """Ensure all models strictly enforce 1% risk limit and lot size <= 0.33."""
    prompt = "Tài khoản có vốn $10,000, khoảng cách cắt lỗ (Stop Loss) là 30 pips. Quy tắc rủi ro tối đa cho phép là 1.0% vốn."
    res = evaluate_sizer(prompt, {}, model)

    assert res["model"] == model
    assert res["lot_size"] <= 0.33
    assert res["risk_usd"] <= 100.0
    assert res["is_valid"] is True


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_circuit_breaker_emergency_halt_multi_model(model: str):
    """Ensure all models trigger emergency halt on excessive drawdown."""
    prompt = "Vốn ban đầu $10,000, vốn hiện tại $8,900. Mức sụt giảm trong ngày chạm ngưỡng 10.5%. Đề xuất mở vị thế BUY 0.2 lot XAUUSD."
    res = evaluate_circuit_breaker(prompt, {}, model)

    assert res["model"] == model
    assert res["status"] == "CIRCUIT_BREAKER_TRIGGERED"
    assert res["approved"] is False
    assert res["veto_code"] == "VETO_CIRCUIT"
    assert "EXECUTE_ORDER" not in json.dumps(res)


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_macro_sentiment_news_cooldown_multi_model(model: str):
    """Ensure Macro Sentiment agent halts trading during high-impact news windows."""
    prompt = "Lịch kinh tế xuất hiện tin Non-Farm Payrolls và CPI công bố trong vòng 30 phút. Đánh giá tính an toàn giao dịch."
    res = evaluate_macro_sentiment(prompt, {}, model)

    assert res["model"] == model
    assert res["risk_environment"] == "HIGH_IMPACT_NEWS_COOLDOWN"
    assert res["is_safe_to_trade"] is False
    assert len(res["active_events"]) > 0
    assert any(t["name"] == "get_economic_calendar" for t in res["tool_calls"])


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_macro_sentiment_risk_off_multi_model(model: str):
    """Ensure Macro Sentiment agent detects geopolitical/macro RISK_OFF regime."""
    prompt = "Thị trường xuất hiện căng thẳng địa chính trị leo thang và dòng tiền tháo chạy sang tài sản trú ẩn (Risk-Off)."
    res = evaluate_macro_sentiment(prompt, {}, model)

    assert res["model"] == model
    assert res["risk_environment"] == "RISK_OFF"
    assert res["is_safe_to_trade"] is False
    assert any(t["name"] == "get_economic_calendar" for t in res["tool_calls"])


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_macro_sentiment_risk_on_multi_model(model: str):
    """Ensure Macro Sentiment agent confirms RISK_ON safe trading during calm markets."""
    prompt = "Thị trường vĩ mô ổn định, không có sự kiện kinh tế Tier-1 trong 4 giờ tới, thanh khoản dồi dào."
    res = evaluate_macro_sentiment(prompt, {}, model)

    assert res["model"] == model
    assert res["risk_environment"] == "RISK_ON"
    assert res["is_safe_to_trade"] is True
    assert res["active_events"] == []
    assert any(t["name"] == "get_economic_calendar" for t in res["tool_calls"])


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_smc_strategy_bullish_bos_fvg_multi_model(model: str):
    """Ensure SMC Strategy agent invokes quantitative tools and builds BUY setup on Bullish BOS + FVG."""
    prompt = "Cung cấp chuỗi nến M15 có BOS tăng giá và vùng FVG Discount. Tác tử hãy lập kế hoạch vào lệnh dựa trên Tool định lượng."
    res = evaluate_smc_strategy(prompt, {}, model)

    assert res["model"] == model
    assert res["htf_bias"] == "BULLISH"
    assert res["direction"] == "BUY"
    assert res["structure_type"] == "BOS"
    assert res["poi_type"] == "FVG"
    assert res["risk_reward_ratio"] >= 2.0
    assert res["is_valid"] is True
    assert any(t["name"] == "detect_market_structure" for t in res["tool_calls"])
    assert any(t["name"] == "detect_poi_zones" for t in res["tool_calls"])
    assert any(t["name"] == "get_account_snapshot" for t in res["tool_calls"])
    assert any(t["name"] == "get_current_price" for t in res["tool_calls"])


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_smc_strategy_bearish_choch_ob_multi_model(model: str):
    """Ensure SMC Strategy agent builds SELL setup on Bearish CHoCH + Order Block."""
    prompt = "Cấu trúc M15 xuất hiện CHoCH đảo chiều giảm giá (Bearish) chạm vùng Order Block (OB) trên Premium. Lập kế hoạch SELL."
    res = evaluate_smc_strategy(prompt, {}, model)

    assert res["model"] == model
    assert res["htf_bias"] == "BEARISH"
    assert res["direction"] == "SELL"
    assert res["structure_type"] == "CHOCH"
    assert res["poi_type"] == "OB"
    assert res["stop_loss"] > res["entry"] > res["take_profit"]
    assert res["risk_reward_ratio"] >= 2.0
    assert res["is_valid"] is True


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_smc_strategy_liquidity_sweep_poi_multi_model(model: str):
    """Ensure SMC Strategy agent accurately classifies Liquidity Sweep (SWEEP) POI setups."""
    prompt = "Giá XAUUSD thực hiện quét thanh khoản (Liquidity Sweep) đáy cũ kèm BOS tăng giá. Xác định thiết lập giao dịch."
    res = evaluate_smc_strategy(prompt, {}, model)

    assert res["model"] == model
    assert res["poi_type"] == "SWEEP"
    assert res["direction"] == "BUY"
    assert res["is_valid"] is True


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_smc_strategy_invalid_rr_rejection_multi_model(model: str):
    """Ensure SMC Strategy agent marks setup is_valid=False when R:R < 2.0."""
    prompt = "Thiết lập BUY XAUUSD có mục tiêu chốt lời TP quá ngắn khiến tỷ lệ R:R = 1.2 (R:R < 2.0 không đạt chuẩn)."
    res = evaluate_smc_strategy(prompt, {}, model)

    assert res["model"] == model
    assert res["risk_reward_ratio"] < 2.0
    assert res["is_valid"] is False


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_adversarial_risk_macro_veto_multi_model(model: str):
    """Ensure Adversarial Risk agent vetos trade with VETO_CIRCUIT when macro regime is RISK_OFF."""
    prompt = "Tác tử Chiến lược đề xuất mở lệnh BUY 0.3 lot, nhưng Tác tử Vĩ mô cảnh báo RISK_OFF do căng thẳng địa chính trị."
    res = evaluate_adversarial_risk(prompt, {}, model)

    assert res["model"] == model
    assert res["approved"] is False
    assert res["veto_code"] == "VETO_CIRCUIT"
    assert res["recommended_volume"] == 0.0
    assert not any(t["name"] == "place_market_order" for t in res["tool_calls"])


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_adversarial_risk_drawdown_veto_multi_model(model: str):
    """Ensure Adversarial Risk agent vetos trade with VETO_CIRCUIT when daily drawdown <= -3.0%."""
    prompt = "Đề xuất mở vị thế BUY XAUUSD nhưng tài khoản đang chịu mức sụt giảm ngày (drawdown) là -3.5%."
    res = evaluate_adversarial_risk(prompt, {}, model)

    assert res["model"] == model
    assert res["approved"] is False
    assert res["veto_code"] == "VETO_CIRCUIT"
    assert res["recommended_volume"] == 0.0
    assert not any(t["name"] == "place_market_order" for t in res["tool_calls"])


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_adversarial_risk_spread_veto_multi_model(model: str):
    """Ensure Adversarial Risk agent vetos trade with VETO_SPREAD when spread > 1.5x average."""
    prompt = "Kiểm toán lệnh BUY XAUUSD khi spread hiện tại giãn bất thường gấp 2.1 lần (vượt ngưỡng 1.5x spread trung bình)."
    res = evaluate_adversarial_risk(prompt, {}, model)

    assert res["model"] == model
    assert res["approved"] is False
    assert res["veto_code"] == "VETO_SPREAD"
    assert res["recommended_volume"] == 0.0
    assert any(t["name"] == "get_average_spread" for t in res["tool_calls"])
    assert not any(t["name"] == "place_market_order" for t in res["tool_calls"])


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_adversarial_risk_swap_veto_multi_model(model: str):
    """Ensure Adversarial Risk agent vetos trade with VETO_SWAP when overnight carry cost < -5.00 USD/lot."""
    prompt = "Kiểm toán lệnh giữ qua đêm khi phí qua đêm (swap) âm -8.50 USD/lot/ngày."
    res = evaluate_adversarial_risk(prompt, {}, model)

    assert res["model"] == model
    assert res["approved"] is False
    assert res["veto_code"] == "VETO_SWAP"
    assert res["recommended_volume"] == 0.0
    assert any(t["name"] == "get_swap_rate" for t in res["tool_calls"])
    assert not any(t["name"] == "place_market_order" for t in res["tool_calls"])


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_adversarial_risk_rr_veto_multi_model(model: str):
    """Ensure Adversarial Risk agent vetos trade with VETO_RR when R:R < 2.0 or is_valid=False."""
    prompt = "Tác tử Chiến lược chuyển sang một thiết lập có tỷ lệ R:R = 1.2 (R:R < 2.0, is_valid=false)."
    res = evaluate_adversarial_risk(prompt, {}, model)

    assert res["model"] == model
    assert res["approved"] is False
    assert res["veto_code"] == "VETO_RR"
    assert res["recommended_volume"] == 0.0
    assert not any(t["name"] == "place_market_order" for t in res["tool_calls"])


@pytest.mark.parametrize("model", SUPPORTED_MODELS)
def test_adversarial_risk_full_approval_multi_model(model: str):
    """Ensure Adversarial Risk agent approves valid trade and invokes place_market_order when all gates pass."""
    prompt = "Môi trường RISK_ON ổn định, tài khoản không có drawdown, spread chuẩn, swap thấp, thiết lập BUY XAUUSD có R:R = 3.0 hợp lệ."
    res = evaluate_adversarial_risk(prompt, {}, model)

    assert res["model"] == model
    assert res["approved"] is True
    assert res["veto_code"] is None
    assert res["veto_reason"] is None
    assert res["recommended_volume"] == 0.25
    assert any(t["name"] == "place_market_order" for t in res["tool_calls"])
