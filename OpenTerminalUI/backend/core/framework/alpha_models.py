import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from backend.core.framework.insight import Insight

class AlphaModel(ABC):
    @abstractmethod
    def generate(self, history: pd.DataFrame, as_of: pd.Timestamp) -> list[Insight]:
        """
        history: DataFrame with DatetimeIndex, columns = symbols, values = adjusted close.
        as_of: Timestamp in history.index.
        """
        pass

class MomentumAlpha(AlphaModel):
    def __init__(self, lookback_days: int = 63):
        self.lookback_days = lookback_days

    def generate(self, history: pd.DataFrame, as_of: pd.Timestamp) -> list[Insight]:
        idx = history.index.get_loc(as_of)
        if idx < self.lookback_days:
            return []
        
        start_idx = idx - self.lookback_days
        # Use data up to and including as_of
        window = history.iloc[start_idx : idx + 1]
        
        returns = (window.iloc[-1] / window.iloc[0]) - 1
        insights = []
        for symbol, ret in returns.items():
            if pd.isna(ret):
                continue
            direction = 1 if ret > 0 else (-1 if ret < 0 else 0)
            confidence = min(1.0, abs(ret) * 5.0)
            insights.append(Insight(
                symbol=str(symbol),
                direction=direction,
                confidence=confidence,
                magnitude=ret
            ))
        return insights

class MeanReversionAlpha(AlphaModel):
    def __init__(self, lookback_days: int = 21, z_entry: float = 1.0):
        self.lookback_days = lookback_days
        self.z_entry = z_entry

    def generate(self, history: pd.DataFrame, as_of: pd.Timestamp) -> list[Insight]:
        idx = history.index.get_loc(as_of)
        if idx < self.lookback_days:
            return []
        
        start_idx = idx - self.lookback_days + 1
        window = history.iloc[start_idx : idx + 1]
        
        mean = window.mean()
        std = window.std()
        latest = window.iloc[-1]
        z_score = (latest - mean) / std
        
        insights = []
        for symbol, z in z_score.items():
            if pd.isna(z) or std[symbol] == 0:
                continue
            
            direction = 0
            if z < -self.z_entry:
                direction = 1
            elif z > self.z_entry:
                direction = -1
            
            confidence = min(1.0, abs(z) / 3.0)
            insights.append(Insight(
                symbol=str(symbol),
                direction=direction,
                confidence=confidence,
                magnitude=-z * std[symbol] / latest[symbol] if latest[symbol] != 0 else 0
            ))
        return insights

class RsiAlpha(AlphaModel):
    def __init__(self, period: int = 14, low: float = 30.0, high: float = 70.0):
        self.period = period
        self.low = low
        self.high = high

    def generate(self, history: pd.DataFrame, as_of: pd.Timestamp) -> list[Insight]:
        idx = history.index.get_loc(as_of)
        # We need at least period + 1 days to compute one RSI value (or more for stabilization)
        # Wilder's RSI typically needs more history. Let's use 2 * period.
        if idx < self.period * 2:
            return []
            
        start_idx = max(0, idx - self.period * 5) # Use extra history for EMA stabilization
        window = history.iloc[start_idx : idx + 1]
        
        insights = []
        for symbol in window.columns:
            prices = window[symbol].dropna()
            if len(prices) < self.period + 1:
                continue
            
            delta = prices.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            
            avg_gain = gain.ewm(com=self.period - 1, min_periods=self.period).mean()
            avg_loss = loss.ewm(com=self.period - 1, min_periods=self.period).mean()
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            latest_rsi = rsi.iloc[-1]
            if pd.isna(latest_rsi):
                continue
                
            direction = 0
            confidence = 0.0
            if latest_rsi < self.low:
                direction = 1
                confidence = min(1.0, (self.low - latest_rsi) / self.low)
            elif latest_rsi > self.high:
                direction = -1
                confidence = min(1.0, (latest_rsi - self.high) / (100 - self.high))
            
            insights.append(Insight(
                symbol=str(symbol),
                direction=direction,
                confidence=confidence
            ))
        return insights
