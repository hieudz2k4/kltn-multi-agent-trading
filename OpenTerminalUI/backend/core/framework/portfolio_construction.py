import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from backend.core.framework.insight import Insight

class PortfolioConstructionModel(ABC):
    @abstractmethod
    def construct(self, insights: list[Insight], history: pd.DataFrame, as_of: pd.Timestamp, 
                  top_n: int, long_only: bool) -> dict[str, float]:
        """
        returns target weights keyed by symbol. Weights sum to <= 1.0.
        """
        pass

class EqualWeighting(PortfolioConstructionModel):
    def construct(self, insights: list[Insight], history: pd.DataFrame, as_of: pd.Timestamp, 
                  top_n: int, long_only: bool) -> dict[str, float]:
        valid_insights = [i for i in insights if i.direction != 0]
        if long_only:
            valid_insights = [i for i in valid_insights if i.direction > 0]
        
        # Sort by confidence to pick top_n
        valid_insights = sorted(valid_insights, key=lambda x: x.confidence, reverse=True)[:top_n]
        
        if not valid_insights:
            return {}
        
        weight = 1.0 / len(valid_insights)
        return {i.symbol: weight * i.direction for i in valid_insights}

class InsightWeighting(PortfolioConstructionModel):
    def construct(self, insights: list[Insight], history: pd.DataFrame, as_of: pd.Timestamp, 
                  top_n: int, long_only: bool) -> dict[str, float]:
        valid_insights = [i for i in insights if i.direction != 0]
        if long_only:
            valid_insights = [i for i in valid_insights if i.direction > 0]
            
        valid_insights = sorted(valid_insights, key=lambda x: x.confidence, reverse=True)[:top_n]
        
        if not valid_insights:
            return {}
        
        total_conf = sum(abs(i.confidence) for i in valid_insights)
        if total_conf == 0:
            return {}
            
        return {i.symbol: (i.confidence * i.direction) / total_conf for i in valid_insights}

class MeanVarianceOptimization(PortfolioConstructionModel):
    def __init__(self, lookback_days: int = 126):
        self.lookback_days = lookback_days

    def construct(self, insights: list[Insight], history: pd.DataFrame, as_of: pd.Timestamp, 
                  top_n: int, long_only: bool) -> dict[str, float]:
        valid_insights = [i for i in insights if i.direction > 0] # Only long for MVO in this simple impl
        valid_insights = sorted(valid_insights, key=lambda x: x.confidence, reverse=True)[:top_n]
        
        if not valid_insights:
            return {}
            
        symbols = [i.symbol for i in valid_insights]
        idx = history.index.get_loc(as_of)
        if idx < self.lookback_days:
            # Fallback to equal weight
            return EqualWeighting().construct(insights, history, as_of, top_n, long_only)
            
        window = history.iloc[idx - self.lookback_days : idx + 1][symbols]
        returns = window.pct_change().dropna()
        
        if returns.empty or returns.shape[1] < 2:
            return EqualWeighting().construct(insights, history, as_of, top_n, long_only)
            
        cov = returns.cov()
        try:
            # Simple Minimum Variance: inv(Cov) @ ones / (ones.T @ inv(Cov) @ ones)
            inv_cov = np.linalg.inv(cov.values)
            ones = np.ones(len(symbols))
            weights = inv_cov @ ones
            weights /= weights.sum()
            
            # Clip to [0, 1] and renormalize
            weights = np.clip(weights, 0, 1)
            if weights.sum() > 0:
                weights /= weights.sum()
            else:
                return EqualWeighting().construct(insights, history, as_of, top_n, long_only)
                
            return {symbols[i]: float(weights[i]) for i in range(len(symbols))}
        except np.linalg.LinAlgError:
            return EqualWeighting().construct(insights, history, as_of, top_n, long_only)
