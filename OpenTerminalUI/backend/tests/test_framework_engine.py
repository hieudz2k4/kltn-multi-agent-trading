import pytest
import pandas as pd
import numpy as np
from backend.core.framework import (
    list_models, build_alpha, run_framework_backtest, FrameworkConfig
)

@pytest.fixture
def synthetic_data():
    np.random.seed(42)
    dates = pd.bdate_range(start='2020-01-01', periods=400)
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']
    
    data = {}
    for i, sym in enumerate(symbols):
        # Create deterministic trends
        # AAPL: Up trend
        # TSLA: Down trend
        # Others: Random walk
        drift = 0.001 if sym == 'AAPL' else (-0.001 if sym == 'TSLA' else 0)
        returns = np.random.normal(drift, 0.015, len(dates))
        prices = 100 * (1 + returns).cumprod()
        data[sym] = prices
        
    df = pd.DataFrame(data, index=dates)
    return df

def test_registry_list_models():
    models = list_models()
    assert 'alpha' in models
    assert 'portfolio_construction' in models
    assert 'risk' in models
    
    for category in ['alpha', 'portfolio_construction', 'risk']:
        assert len(models[category]) > 0
        for item in models[category]:
            assert 'id' in item
            assert 'label' in item
            assert 'params' in item

def test_run_momentum_backtest(synthetic_data):
    config = FrameworkConfig(
        alpha={'id': 'momentum', 'params': {'lookback_days': 63}},
        portfolio_construction={'id': 'equal', 'params': {}},
        risk=[],
        rebalance_freq='ME'
    )
    
    results = run_framework_backtest(synthetic_data, config)
    
    assert 'summary' in results
    assert 'equity_curve' in results
    assert 'holdings' in results
    assert 'insights' in results
    
    assert len(results['equity_curve']) > 0
    assert results['equity_curve'][0]['strategy'] == 1.0
    
    strategy_metrics = results['summary']['strategy']
    assert 'sharpe' in strategy_metrics
    assert 'max_drawdown' in strategy_metrics

def test_maximum_drawdown_risk(synthetic_data):
    # No risk run
    config_no_risk = FrameworkConfig(
        alpha={'id': 'momentum', 'params': {'lookback_days': 63}},
        portfolio_construction={'id': 'equal', 'params': {}},
        risk=[],
        rebalance_freq='W'
    )
    results_no_risk = run_framework_backtest(synthetic_data, config_no_risk)
    
    # High risk (forces liquidation on small DD)
    config_with_risk = FrameworkConfig(
        alpha={'id': 'momentum', 'params': {'lookback_days': 63}},
        portfolio_construction={'id': 'equal', 'params': {}},
        risk=[{'id': 'max_drawdown', 'params': {'max_drawdown': 0.0001}}],
        rebalance_freq='W'
    )
    results_with_risk = run_framework_backtest(synthetic_data, config_with_risk)
    
    # Check if weights become empty at some point
    any_empty = any(len(h['weights']) == 0 for h in results_with_risk['holdings'][1:])
    assert any_empty

def test_mean_variance_optimization(synthetic_data):
    config = FrameworkConfig(
        alpha={'id': 'momentum', 'params': {'lookback_days': 63}},
        portfolio_construction={'id': 'mean_variance', 'params': {'lookback_days': 126}},
        risk=[],
        rebalance_freq='ME'
    )
    
    results = run_framework_backtest(synthetic_data, config)
    assert 'summary' in results
    
    for h in results['holdings']:
        weights = h['weights'].values()
        if weights:
            assert sum(weights) <= 1.0 + 1e-5

def test_build_alpha_error():
    with pytest.raises(ValueError, match="Unknown alpha model id: bogus"):
        build_alpha({'id': 'bogus'})
