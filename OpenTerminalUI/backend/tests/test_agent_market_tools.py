import pytest
import pandas as pd
import backend.agent.tools.market_tools as mt
from backend.agent.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_screen_stocks_calls_engine(monkeypatch):
    captured = {}

    class FakeEngine:
        def run(self, config):
            captured["query"] = config.query
            captured["limit"] = config.limit
            return {
                "results": [{"ticker": "AAPL", "company": "Apple", "pe": 18, "roe": 30}],
                "total_results": 1,
                "query_parsed": "pe < 20",
            }

    async def fake_hydrate(universe, market):
        captured["hydrated"] = (universe, market)
        return 3

    monkeypatch.setattr(mt, "ScreenerEngine", lambda: FakeEngine())
    monkeypatch.setattr(mt, "_hydrate_missing_universe_rows", fake_hydrate)
    out = await mt.screen_stocks({"query": "pe_ratio < 20", "limit": 5, "market": "US", "universe": "sp_500"})
    assert captured["query"] == "pe < 20"
    assert captured["limit"] == 5
    # The tool must hydrate before running, else the materialized store is empty.
    assert captured["hydrated"] == ("sp_500", "US")
    assert out["count"] == 1
    assert out["filters_applied"]["expression"] == "pe < 20"
    assert out["analysis"]["matched"] == 1
    assert out["top_candidates"][0]["fit_reasons"] == ["P/E 18.0", "ROE 30.0%"]
    assert out["results"][0]["ticker"] == "AAPL"
    assert out["results"][0]["roe"] == 30


@pytest.mark.asyncio
async def test_screen_stocks_normalizes_agent_field_aliases(monkeypatch):
    captured = {}

    class FakeEngine:
        def run(self, config):
            captured["query"] = config.query
            return {"results": [], "total_results": 0, "query_parsed": config.query}

    async def fake_hydrate(universe, market):
        return 0

    monkeypatch.setattr(mt, "ScreenerEngine", lambda: FakeEngine())
    monkeypatch.setattr(mt, "_hydrate_missing_universe_rows", fake_hydrate)
    out = await mt.screen_stocks({"query": "roe_pct > 15 and pe_ratio < 20 and debt_to_equity < 0.5", "market": "US", "universe": "sp_500"})
    assert captured["query"] == "roe > 15 and pe < 20 and debt_equity < 0.5"
    assert out["filters_applied"]["raw_expression"] == "roe_pct > 15 and pe_ratio < 20 and debt_to_equity < 0.5"
    assert out["filters_applied"]["expression"] == "roe > 15 and pe < 20 and debt_equity < 0.5"


@pytest.mark.asyncio
async def test_get_stock_snapshot(monkeypatch):
    async def fake_fetcher():
        class F:
            async def fetch_stock_snapshot(self, sym):
                return {"company_name": "Apple", "last_price": 200.0, "symbol": sym}
        return F()

    monkeypatch.setattr(mt, "get_unified_fetcher", fake_fetcher)
    out = await mt.get_stock_snapshot({"ticker": "aapl"})
    assert out["symbol"] == "AAPL"
    assert out["last_price"] == 200.0


@pytest.mark.asyncio
async def test_compare_stocks(monkeypatch):
    async def fake_fetcher():
        class F:
            async def fetch_stock_snapshot(self, sym):
                return {"symbol": sym, "pe_ratio": 10 if sym == "A" else 20}
        return F()

    monkeypatch.setattr(mt, "get_unified_fetcher", fake_fetcher)
    out = await mt.compare_stocks({"tickers": ["A", "B"], "metrics": ["pe_ratio"]})
    assert len(out["rows"]) == 2
    assert out["rows"][0]["pe_ratio"] == 10


def test_build_default_registry_has_read_tools():
    reg = mt.build_default_registry()
    names = {d.name for d in reg.tool_defs()}
    assert {"screen_stocks", "get_stock_snapshot", "compare_stocks", "analyze_technicals", "scan_setups", "backtest_symbol", "backtest_basket", "validate_backtest"} <= names
    for d in reg.tool_defs():
        assert reg.get(d.name).read_only is True


@pytest.mark.asyncio
async def test_analyze_technicals_returns_compact_snapshot(monkeypatch):
    index = pd.date_range("2025-01-01", periods=30, freq="D")
    frame = pd.DataFrame({
        "Open": range(100, 130), "High": range(101, 131), "Low": range(99, 129),
        "Close": range(100, 130), "Volume": [1_000_000] * 30,
    }, index=index)

    class Fetcher:
        async def fetch_history(self, *args, **kwargs):
            return {"chart": {}}

    async def fake_fetcher():
        return Fetcher()

    monkeypatch.setattr(mt, "get_unified_fetcher", fake_fetcher)
    monkeypatch.setattr(mt, "_parse_yahoo_chart", lambda raw: frame)
    out = await mt.analyze_technicals({"ticker": "aapl"})
    assert out["ticker"] == "AAPL"
    assert out["price"] == 129.0
    assert "trend" in out


@pytest.mark.asyncio
async def test_analyze_technicals_empty_history_has_note(monkeypatch):
    class Fetcher:
        async def fetch_history(self, *args, **kwargs):
            return {"chart": {}}

    async def fake_fetcher():
        return Fetcher()

    monkeypatch.setattr(mt, "get_unified_fetcher", fake_fetcher)
    monkeypatch.setattr(mt, "_parse_yahoo_chart", lambda raw: pd.DataFrame())
    out = await mt.analyze_technicals({"ticker": "AAPL"})
    assert out["active_setups"] == []
    assert out["note"]


@pytest.mark.asyncio
async def test_scan_setups_trims_results(monkeypatch):
    class Bundle:
        summary = {"symbols_scanned": 12, "matches": 1}
        results = [{
            "symbol": "AAPL", "setup_type": "TREND_RETEST", "score": 0.9,
            "event_type": "triggered", "trend_state": "up", "rvol": 1.8,
            "atr_pct": 2.3, "distance_to_trigger": 0.01, "levels": {"too": "large"},
        }]

    class FakeRunner:
        def __init__(self, fetcher):
            pass

        async def run(self, preset, symbol_cap, concurrency):
            return Bundle()

    async def fake_fetcher():
        return object()

    monkeypatch.setattr(mt, "get_unified_fetcher", fake_fetcher)
    monkeypatch.setattr(mt, "ScannerRunner", FakeRunner)
    out = await mt.scan_setups({"universe": "US:SP500"})
    assert out["matches"] == 1
    assert set(out["results"][0]) == {"symbol", "setup_type", "score", "event_type", "trend_state", "rvol", "atr_pct", "distance_to_trigger"}


@pytest.mark.asyncio
async def test_backtest_symbol_returns_compact_result(monkeypatch):
    index = pd.date_range("2024-01-01", periods=120, freq="D")
    close = [100 + i * 0.25 + (3 if i % 13 < 6 else -3) for i in range(120)]
    frame = pd.DataFrame({
        "Open": close, "High": [v + 1 for v in close], "Low": [v - 1 for v in close],
        "Close": close, "Volume": [1_000_000] * 120,
    }, index=index)

    class Fetcher:
        async def fetch_history(self, *args, **kwargs):
            return {"chart": {}}

    async def fake_fetcher():
        return Fetcher()

    monkeypatch.setattr(mt, "get_unified_fetcher", fake_fetcher)
    monkeypatch.setattr(mt, "_parse_yahoo_chart", lambda raw: frame)
    out = await mt.backtest_symbol({"ticker": "aapl", "short_window": 5, "long_window": 15})
    assert isinstance(out["metrics"]["sharpe"], float)
    assert isinstance(out["metrics"]["max_drawdown_pct"], float)
    assert len(out["equity_curve"]) <= 120


@pytest.mark.asyncio
async def test_backtest_symbol_empty_history_has_note(monkeypatch):
    class Fetcher:
        async def fetch_history(self, *args, **kwargs):
            return {"chart": {}}

    async def fake_fetcher():
        return Fetcher()

    monkeypatch.setattr(mt, "get_unified_fetcher", fake_fetcher)
    monkeypatch.setattr(mt, "_parse_yahoo_chart", lambda raw: pd.DataFrame())
    out = await mt.backtest_symbol({"ticker": "AAPL"})
    assert out["note"]


@pytest.mark.asyncio
async def test_backtest_basket_trims_result(monkeypatch):
    index = pd.date_range("2024-01-01", periods=180, freq="D")
    equity = pd.DataFrame({"strategy": range(1, 181), "benchmark": range(2, 182)}, index=index)

    def fake_backtest(*args, **kwargs):
        return {"equity_curve": equity, "holdings": pd.DataFrame(), "summary": {
            "strategy": {"total_return": 0.2, "cagr": 0.1, "volatility": 0.15, "sharpe": 1.1, "max_drawdown": -0.08},
            "benchmark": {"total_return": 0.1, "cagr": 0.05, "volatility": 0.12, "sharpe": 0.7, "max_drawdown": -0.1},
            "alpha_total_return": 0.1,
        }}

    monkeypatch.setattr(mt, "backtest_momentum_rotation", fake_backtest)
    out = await mt.backtest_basket({"tickers": ["AAPL", "MSFT"], "market": "US"})
    assert "summary" in out
    assert len(out["equity_curve"]) <= 120
    assert set(out["equity_curve"][0]) == {"date", "strategy", "benchmark"}


@pytest.mark.asyncio
async def test_backtest_basket_value_error_has_note(monkeypatch):
    def failing_backtest(*args, **kwargs):
        raise ValueError("No price data")

    monkeypatch.setattr(mt, "backtest_momentum_rotation", failing_backtest)
    out = await mt.backtest_basket({"tickers": ["AAPL", "MSFT"]})
    assert out["note"]


@pytest.mark.asyncio
async def test_validate_backtest_returns_compact_robustness_result():
    curve = [
        {"date": str(date.date()), "equity": 100 + index * 0.5}
        for index, date in enumerate(pd.date_range("2024-01-01", periods=250, freq="D"))
    ]
    out = await mt.validate_backtest({"equity_curve": curve})
    assert isinstance(out["permutation"]["p_value"], float)
    assert "consistency_score" in out["robustness"]
    assert out["verdict"]
    assert "distribution" not in out["permutation"]


@pytest.mark.asyncio
async def test_validate_backtest_normalizes_basket_curve():
    curve = [
        {"date": str(date.date()), "strategy": 100 + index, "benchmark": 100 + index * 0.5}
        for index, date in enumerate(pd.date_range("2024-01-01", periods=20, freq="D"))
    ]
    out = await mt.validate_backtest({"equity_curve": curve, "n_permutations": 100})
    assert out["points"] > 0


@pytest.mark.asyncio
async def test_validate_backtest_short_curve_has_note():
    out = await mt.validate_backtest({"equity_curve": [{"date": "2024-01-01", "equity": 100}]})
    assert out["note"]
