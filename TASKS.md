# Task Governance & Execution Tracklist

## Project: kltn-multi-agent-trading
- **Status**: IN_PROGRESS
- **Active Task**: TASK-03-MULTI-AGENT-ARCH
- **WIP Limit**: 1

---

## Task Board

| Task ID | Description | Status | Evidence / Output |
| :--- | :--- | :--- | :--- |
| `TASK-01-REQUIREMENTS-SPEC` | Xây dựng tài liệu đặc tả yêu cầu hệ thống Multi-Agent Trading (`REQUIREMENTS.md`) | COMPLETED | `REQUIREMENTS.md` |
| `TASK-02-C4-DESIGN` | Mô hình hóa kiến trúc theo chuẩn C4 (Context, Container, Component, Code) | COMPLETED | `C4-Documentation/` |
| `TASK-03-MULTI-AGENT-ARCH` | Thiết kế chi tiết logic Agent, State Machine, Tool Contracts và Veto Rules | COMPLETED | `src/core/`, `src/tools/`, `src/agents/smc/`, `src/agents/shared/`, `tests/test_smc_pipeline.py` |
| `TASK-04-IMPLEMENTATION` | Hiện thực hóa mã nguồn tích hợp TradingView CDP 9222 và MT5 RPyC 8001 | PENDING | `src/` |
| `TASK-05-BACKTEST-EVAL` | Thực nghiệm Backtest và đo lường chỉ số định lượng (PnL, Sharpe, Drawdown) | PENDING | `tests/`, `reports/` |
| `TASK-06-FINAL-DOCS` | Hoàn thiện Báo cáo Thuyết minh Khóa luận Tốt nghiệp (`docs-architect`) | PENDING | `REPORT.md` |

---

## Current Checkpoint
- **State**: Hoàn thành toàn diện `TASK-03-MULTI-AGENT-ARCH` — Toàn bộ 5 tác tử SMC (`htf_bias`, `structure`, `poi`, `sizer`, `risk_gatekeeper`), `circuit_breaker`, `smc_orchestrator` và bộ test unit/live dry run đã pass 100%.
- **Next Action**: Chuyển sang `TASK-04-IMPLEMENTATION`: Hoàn thiện main loop daemon 15-phút tự động quét watchlist và kết nối VPS live.
