import pytest
import pandas as pd
import numpy as np
from backend.core.framework.risk_management import TakeProfitRisk, CooldownRisk, ScalingRisk
from backend.core.framework.engine import FrameworkConfig, run_framework_backtest

def test_take_profit_risk():
    # Long position +30% with take_profit_pct=0.25, exit_fraction=1.0 -> target becomes 0.0
    # +10% -> unchanged
    tp_risk = TakeProfitRisk(take_profit_pct=0.25, exit_fraction=1.0)
    
    targets = {'AAPL': 0.5, 'MSFT': 0.5}
    state = {
        'current_weights': {'AAPL': 0.5, 'MSFT': 0.5},
        'prices': {'AAPL': 130, 'MSFT': 110},
        'entry_prices': {'AAPL': 100, 'MSFT': 100}
    }
    
    # AAPL ret = 30% >= 25% -> should be reduced by 100%
    # MSFT ret = 10% < 25% -> should be unchanged
    adjusted = tp_risk.evaluate(targets, state)
    assert adjusted['AAPL'] == 0.0
    assert adjusted['MSFT'] == 0.5
    
    # Short position -30% (gain)
    tp_risk_short = TakeProfitRisk(take_profit_pct=0.25, exit_fraction=0.5)
    targets_short = {'AAPL': -0.5}
    state_short = {
        'current_weights': {'AAPL': -0.5},
        'prices': {'AAPL': 70},
        'entry_prices': {'AAPL': 100}
    }
    # ret = 70/100 - 1 = -30% <= -25% -> should be reduced by 50%
    adjusted_short = tp_risk_short.evaluate(targets_short, state_short)
    assert adjusted_short['AAPL'] == -0.25

def test_cooldown_risk():
    # Cooldown(cooldown_bars=2): a close (current_weight=1.0, target=0.0) starts cooldown; 
    # next evaluate with a buy target>0 is forced to 0.0; the next allows the buy through.
    cd_risk = CooldownRisk(cooldown_bars=2)
    
    # Bar 0: Close position
    targets0 = {'AAPL': 0.0}
    state0 = {'current_weights': {'AAPL': 1.0}}
    adj0 = cd_risk.evaluate(targets0, state0)
    assert adj0['AAPL'] == 0.0
    # cooldown_bars=2, set to 2, then decremented to 1
    assert cd_risk._cooldown['AAPL'] == 1
    
    # Bar 1: Try to re-enter (Cooldown starts at 1, blocks, then decremented to 0/dropped)
    targets1 = {'AAPL': 0.5}
    state1 = {'current_weights': {'AAPL': 0.0}}
    adj1 = cd_risk.evaluate(targets1, state1)
    assert adj1['AAPL'] == 0.0
    assert 'AAPL' not in cd_risk._cooldown
    
    # Bar 2: Re-enter successfully (Cooldown starts empty)
    targets2 = {'AAPL': 0.5}
    state2 = {'current_weights': {'AAPL': 0.0}}
    adj2 = cd_risk.evaluate(targets2, state2)
    assert adj2['AAPL'] == 0.5

def test_scaling_risk():
    # Scaling(step_pct=0.05, max_entries=2, scale_increment=0.25, cooldown_bars=1)
    scale_risk = ScalingRisk(step_pct=0.05, max_entries=2, scale_increment=0.25, cooldown_bars=1)
    
    # Bar 0: No gains yet
    targets0 = {'AAPL': 0.1}
    state0 = {
        'prices': {'AAPL': 100},
        'entry_prices': {'AAPL': 100}
    }
    adj0 = scale_risk.evaluate(targets0, state0)
    assert adj0['AAPL'] == 0.1
    
    # Bar 1: +6% gain -> Scale Up (Entry 1)
    state1 = {
        'prices': {'AAPL': 106},
        'entry_prices': {'AAPL': 100}
    }
    adj1 = scale_risk.evaluate(targets0, state1)
    assert adj1['AAPL'] == 0.1 * 1.25
    assert scale_risk._entries['AAPL'] == 1
    # cooldown_bars=1, set to 1, then decremented to 0 (dropped)
    assert 'AAPL' not in scale_risk._cooldown
    
    # Bar 2: +12% gain, cooldown was 0 -> Scale Up (Entry 2)
    state2 = {
        'prices': {'AAPL': 112},
        'entry_prices': {'AAPL': 100}
    }
    adj2 = scale_risk.evaluate(targets0, state2)
    assert adj2['AAPL'] == 0.1 * 1.25
    assert scale_risk._entries['AAPL'] == 2

    # Bar 3: +20% gain but max_entries reached
    state3 = {
        'prices': {'AAPL': 120},
        'entry_prices': {'AAPL': 100}
    }
    adj3 = scale_risk.evaluate(targets0, state3)
    assert adj3['AAPL'] == 0.1

def test_engine_cost_equivalence():
    # run_framework_backtest with empty overrides equals behavior with overrides absent
    dates = pd.bdate_range(start='2020-01-01', periods=10)
    prices = pd.DataFrame({'AAPL': [100 + i for i in range(10)], 
                           'MSFT': [100 - i for i in range(10)]}, index=dates)
    
    config_base = FrameworkConfig(
        alpha={'id': 'momentum', 'params': {'lookback_days': 2}},
        portfolio_construction={'id': 'equal', 'params': {}},
        rebalance_freq='D',
        transaction_cost_bps=10.0
    )
    
    config_overrides_empty = FrameworkConfig(
        alpha={'id': 'momentum', 'params': {'lookback_days': 2}},
        portfolio_construction={'id': 'equal', 'params': {}},
        rebalance_freq='D',
        transaction_cost_bps=10.0,
        transaction_cost_overrides={}
    )
    
    res_base = run_framework_backtest(prices, config_base)
    res_empty = run_framework_backtest(prices, config_overrides_empty)
    
    assert res_base['equity_curve'][-1]['strategy'] == res_empty['equity_curve'][-1]['strategy']

    # Test actual override
    config_overrides = FrameworkConfig(
        alpha={'id': 'momentum', 'params': {'lookback_days': 2}},
        portfolio_construction={'id': 'equal', 'params': {}},
        rebalance_freq='D',
        transaction_cost_bps=10.0,
        transaction_cost_overrides={'AAPL': 100.0} # 10x cost for AAPL
    )
    res_overrides = run_framework_backtest(prices, config_overrides)
    assert res_overrides['equity_curve'][-1]['strategy'] < res_base['equity_curve'][-1]['strategy']
