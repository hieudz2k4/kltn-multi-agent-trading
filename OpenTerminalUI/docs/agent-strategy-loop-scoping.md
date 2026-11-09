# Scoping note — #4: Strategy-coding / backtest agent loop

Status: **proposed** (not started). Sourced from the `awesome-trading-agents` patterns
(pwb-alphaevolve, QuantGPT). This is the one remaining item from that list after #1 debate,
#2 MCP server, and #3 shared playbook shipped.

## Goal

An agent that **proposes a strategy or parameter set, backtests it against the existing Model Lab /
backtester, reads the metrics, and iterates** — closing the loop from idea → tested result without a
human running each backtest by hand.

## Why it's feasible here

The execution substrate already exists; this is mostly a *tool + control-loop* layer, not new infra:

- `backend/model_lab/service.py` already exposes: `create_experiment`, `enqueue_run`, `get_run`,
  `get_report` (Sharpe/return/drawdown/etc.), `param_sweep`, `walk_forward`, `compare`, `leaderboard`.
- `backend/core/*backtest*.py` + `backend/portfolio_backtests/engine.py` run the actual backtests.
- The agent framework (registry + Orchestrator + playbook + debate) is in place and read-only-safe.

So #4 = wrap a few Model Lab service methods as agent tools + an iterate-until-better control loop.

## Proposed design (v1, bounded)

1. **New tools** (`backend/agent/tools/strategy_tools.py`), thin wrappers over `ModelLabService`:
   - `list_strategies()` → available model keys / templates.
   - `run_backtest(model_key, params, window)` → `create_experiment` + `enqueue_run` + await
     `get_report`; return the metric summary (Sharpe, CAGR, max DD, win rate).
   - `param_sweep(model_key, grid)` → existing `param_sweep` (bounded `max_combinations`).
   - `leaderboard(sort_by)` → existing `leaderboard`.
2. **A `StrategyLoopOrchestrator`** (mirrors `DebateOrchestrator`): propose params → `run_backtest` →
   read metrics → propose an improvement → repeat up to N rounds or until a target metric stops
   improving. Streams the same `phase` / `role_message` / `tool_call` events the console already renders.
3. **Playbook role** (`backend/agent/playbook.py`): a `STRATEGY_RESEARCHER` persona composing the shared
   evidence discipline + a "form a hypothesis, change one variable, compare to baseline" rule.
4. **Flag-gated** (`agent_strategy_loop_enabled`, default off), read-only (backtests only — never
   touches OMS / paper-trading / live orders).

## Hard constraints / risks (the reason this is a separate, careful build)

- **Cost & time**: each iteration is a full backtest (seconds–minutes) + an LLM call. A 5-round loop
  with a param sweep can be minutes long and many tokens. Must cap rounds, sweep size, and wall-clock,
  and run backtests via the existing async job queue (`backend/services/backtest_jobs.py`) — not inline.
- **Overfitting**: an agent optimizing Sharpe on one window will curve-fit. v1 must **require
  `walk_forward` (out-of-sample) validation** before a result is reported as "good", and surface the
  train/test gap. This is the single most important correctness guardrail.
- **Execution safety**: the loop must be physically unable to reach order/execution tools — enforce via
  a dedicated registry containing only the read-only strategy/backtest tools (not `build_default_registry`
  + order tools).
- **Determinism for tests**: backtests must be seeded/fixture-backed so unit tests don't depend on live
  market data.

## Estimated effort

Multi-session. Roughly: tools wrapper (~0.5), loop orchestrator + streaming (~1), walk-forward guardrail
(~0.5), frontend surfacing of iterations/leaderboard (~0.5), tests + live verification (~0.5). Bigger
than #1–#3 combined, mostly because of the overfitting guardrail and job-queue integration.

## Recommendation

Build v1 **read-only, walk-forward-validated, flag-gated**, reusing the Model Lab service as-is. Defer
any "agent writes new strategy *code*" (AlphaEvolve-style codegen) to a later v2 — that adds arbitrary
code execution risk and should not be in the first cut.
