import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Any
from backend.core.framework.registry import build_alpha, build_portfolio_construction, build_risk

@dataclass
class FrameworkConfig:
    alpha: dict                         # {'id','params'}
    portfolio_construction: dict        # {'id','params'}
    risk: list[dict] = field(default_factory=list)
    rebalance_freq: str = "ME"          # pandas offset alias (ME/QE/W etc.)
    initial_cash: float = 100000.0
    transaction_cost_bps: float = 10.0
    transaction_cost_overrides: dict = field(default_factory=dict) # per-symbol bps
    top_n: int = 10
    long_only: bool = True

def run_framework_backtest(prices: pd.DataFrame, config: FrameworkConfig,
                           benchmark: pd.Series | None = None) -> dict:
    if prices.empty:
        raise ValueError("No usable price data")
        
    prices = prices.ffill().dropna(axis=1, how='all')
    if prices.empty:
        raise ValueError("No usable price data")

    alpha_model = build_alpha(config.alpha)
    pc_model = build_portfolio_construction(config.portfolio_construction)
    risk_models = build_risk(config.risk)

    # Determine rebalance dates
    # We want the last available price date in each resample period
    rebalance_dates = prices.groupby(pd.Grouper(freq=config.rebalance_freq)).apply(lambda x: x.index[-1] if not x.empty else None)
    rebalance_dates = pd.DatetimeIndex(rebalance_dates.dropna().unique())
    
    if rebalance_dates.empty or rebalance_dates[0] != prices.index[0]:
        rebalance_dates = prices.index[0:1].union(rebalance_dates)

    equity = config.initial_cash
    peak_equity = equity
    current_weights = {sym: 0.0 for sym in prices.columns}
    entry_prices = {sym: 0.0 for sym in prices.columns}
    
    equity_curve = []
    holdings_history = []
    insights_history = []
    
    returns = prices.pct_change().fillna(0)

    # Align benchmark to the strategy's trading calendar so per-day lookups never
    # KeyError on mismatched dates (real data has holiday/missing-bar gaps).
    if benchmark is not None:
        benchmark = benchmark.reindex(prices.index).ffill().bfill()

    current_date_idx = 0
    total_alpha_return = 0.0
    
    for i, rb_date in enumerate(rebalance_dates):
        # 1. Update equity and state until rb_date
        next_rb_date = rebalance_dates[i+1] if i+1 < len(rebalance_dates) else prices.index[-1]
        
        # Period dates (exclusive of current rb_date, inclusive of next_rb_date)
        period_mask = (prices.index > rb_date) & (prices.index <= next_rb_date)
        period_dates = prices.index[period_mask]
        
        # --- REBALANCE AT rb_date ---
        # State at rb_date
        state = {
            'equity': equity,
            'peak_equity': peak_equity,
            'current_weights': current_weights.copy(),
            'prices': prices.loc[rb_date].to_dict(),
            'entry_prices': entry_prices.copy()
        }
        
        # Generate Insights
        insights = alpha_model.generate(prices, rb_date)
        for ins in insights:
            insights_history.append({
                'date': rb_date.strftime('%Y-%m-%d'),
                'symbol': ins.symbol,
                'direction': ins.direction,
                'confidence': round(float(ins.confidence), 6),
                'magnitude': round(float(ins.magnitude), 6)
            })
            
        # Construct Target Weights
        targets = pc_model.construct(insights, prices, rb_date, config.top_n, config.long_only)
        
        # Apply Risk Models
        for risk_model in risk_models:
            targets = risk_model.evaluate(targets, state)
            
        # Standardize targets (ensure all symbols present)
        new_weights = {sym: 0.0 for sym in prices.columns}
        for sym, w in targets.items():
            if sym in new_weights:
                new_weights[sym] = w
                
        # Compute Turnover and Transaction Costs
        cost = 0.0
        for sym in prices.columns:
            bps = config.transaction_cost_overrides.get(sym, config.transaction_cost_bps)
            diff = abs(new_weights[sym] - current_weights[sym])
            cost += (bps / 10000.0) * diff * equity
            
        turnover = sum(abs(new_weights[sym] - current_weights[sym]) for sym in prices.columns)
        equity -= cost
        
        # Update entry prices for new positions
        for sym in prices.columns:
            if new_weights[sym] != 0 and current_weights[sym] == 0:
                entry_prices[sym] = prices.loc[rb_date, sym]
            elif new_weights[sym] == 0:
                entry_prices[sym] = 0.0
                
        current_weights = new_weights
        holdings_history.append({
            'rebalance_date': rb_date.strftime('%Y-%m-%d'),
            'weights': {sym: round(w, 6) for sym, w in current_weights.items() if w != 0},
            'turnover': round(float(turnover), 6)
        })

        # Add rb_date to equity curve if it's the first one
        if i == 0:
            equity_curve.append({
                'date': rb_date.strftime('%Y-%m-%d'),
                'strategy': round(equity / config.initial_cash, 6),
                'benchmark': 1.0 if benchmark is not None else None
            })

        # --- EVOLVE UNTIL NEXT REBALANCE ---
        for dt in period_dates:
            day_return = sum(current_weights[sym] * returns.loc[dt, sym] for sym in prices.columns)
            equity *= (1 + day_return)
            peak_equity = max(peak_equity, equity)
            
            bm_val = None
            if benchmark is not None:
                # Assuming benchmark is a price series, normalize it
                bm_val = round(benchmark.loc[dt] / benchmark.iloc[0], 6)
                
            equity_curve.append({
                'date': dt.strftime('%Y-%m-%d'),
                'strategy': round(equity / config.initial_cash, 6),
                'benchmark': bm_val
            })

    # Summary Metrics
    strategy_curve = pd.Series([point['strategy'] for point in equity_curve], 
                               index=pd.to_datetime([point['date'] for point in equity_curve]))
    
    def calc_metrics(curve: pd.Series):
        if curve.empty: return {}
        total_return = (curve.iloc[-1] / curve.iloc[0]) - 1
        days = (curve.index[-1] - curve.index[0]).days
        cagr = (1 + total_return) ** (365.25 / days) - 1 if days > 0 else 0
        
        daily_rets = curve.pct_change().dropna()
        vol = daily_rets.std() * np.sqrt(252)
        sharpe = (cagr / vol) if vol > 0 else 0
        
        drawdown = (curve / curve.cummax()) - 1
        max_dd = drawdown.min()
        
        return {
            'total_return': round(float(total_return), 6),
            'cagr': round(float(cagr), 6),
            'volatility': round(float(vol), 6),
            'sharpe': round(float(sharpe), 6),
            'max_drawdown': round(float(max_dd), 6)
        }

    summary = {'strategy': calc_metrics(strategy_curve)}
    if benchmark is not None:
        benchmark_normalized = benchmark / benchmark.iloc[0]
        summary['benchmark'] = calc_metrics(benchmark_normalized)
    else:
        summary['benchmark'] = None

    # Excess return over benchmark (true "alpha"); falls back to strategy return when no benchmark.
    if summary['benchmark']:
        summary['alpha_total_return'] = round(
            summary['strategy']['total_return'] - summary['benchmark']['total_return'], 6
        )
    else:
        summary['alpha_total_return'] = summary['strategy']['total_return']

    return {
        'summary': summary,
        'equity_curve': equity_curve,
        'holdings': holdings_history,
        'insights': insights_history
    }
