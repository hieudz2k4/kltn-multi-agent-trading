import pandas as pd
import numpy as np
from abc import ABC, abstractmethod

class RiskManagementModel(ABC):
    @abstractmethod
    def evaluate(self, targets: dict[str, float], state: dict) -> dict[str, float]:
        """
        targets: current target weights.
        state: {'equity': float, 'peak_equity': float, 'current_weights': dict, 
                'prices': dict, 'entry_prices': dict}.
        returns adjusted target weights.
        """
        pass

class MaximumDrawdownRisk(RiskManagementModel):
    def __init__(self, max_drawdown: float = 0.2):
        self.max_drawdown = max_drawdown

    def evaluate(self, targets: dict[str, float], state: dict) -> dict[str, float]:
        equity = state.get('equity', 1.0)
        peak = state.get('peak_equity', 1.0)
        if peak > 0:
            dd = (equity / peak) - 1
            if dd <= -self.max_drawdown:
                return {} # Liquidate everything
        return targets

class MaxPositionSizeRisk(RiskManagementModel):
    def __init__(self, max_weight: float = 0.25):
        self.max_weight = max_weight

    def evaluate(self, targets: dict[str, float], state: dict) -> dict[str, float]:
        adjusted = {}
        for sym, weight in targets.items():
            if weight > self.max_weight:
                adjusted[sym] = self.max_weight
            elif weight < -self.max_weight:
                adjusted[sym] = -self.max_weight
            else:
                adjusted[sym] = weight
        return adjusted

class TrailingStopRisk(RiskManagementModel):
    def __init__(self, stop_pct: float = 0.15):
        self.stop_pct = stop_pct

    def evaluate(self, targets: dict[str, float], state: dict) -> dict[str, float]:
        current_weights = state.get('current_weights', {})
        prices = state.get('prices', {})
        entry_prices = state.get('entry_prices', {})
        
        adjusted = targets.copy()
        for sym in current_weights:
            if current_weights[sym] == 0:
                continue
            
            price = prices.get(sym)
            entry = entry_prices.get(sym)
            
            if price is None or entry is None:
                continue
                
            # Long position
            if current_weights[sym] > 0:
                if (price / entry) - 1 <= -self.stop_pct:
                    adjusted[sym] = 0.0
            # Short position
            elif current_weights[sym] < 0:
                if (price / entry) - 1 >= self.stop_pct:
                    adjusted[sym] = 0.0
                    
        return adjusted

class TakeProfitRisk(RiskManagementModel):
    def __init__(self, take_profit_pct: float = 0.25, exit_fraction: float = 1.0):
        self.take_profit_pct = take_profit_pct
        self.exit_fraction = max(0.0, min(1.0, exit_fraction))

    def evaluate(self, targets: dict[str, float], state: dict) -> dict[str, float]:
        current_weights = state.get('current_weights', {})
        prices = state.get('prices', {})
        entry_prices = state.get('entry_prices', {})
        adjusted = targets.copy()

        for sym, weight in current_weights.items():
            if weight == 0:
                continue
            
            price = prices.get(sym)
            entry = entry_prices.get(sym)
            if price is None or entry is None or entry <= 0:
                continue

            ret = (price / entry) - 1
            # Long
            if weight > 0 and ret >= self.take_profit_pct:
                adjusted[sym] = targets.get(sym, 0.0) * (1 - self.exit_fraction)
            # Short
            elif weight < 0 and ret <= -self.take_profit_pct:
                adjusted[sym] = targets.get(sym, 0.0) * (1 - self.exit_fraction)

        return adjusted

class CooldownRisk(RiskManagementModel):
    def __init__(self, cooldown_bars: int = 3):
        self.cooldown_bars = cooldown_bars
        self._cooldown: dict[str, int] = {}

    def evaluate(self, targets: dict[str, float], state: dict) -> dict[str, float]:
        adjusted = targets.copy()
        current_weights = state.get('current_weights', {})

        # 1. Block entry for symbols in cooldown
        for sym in list(self._cooldown.keys()):
            if self._cooldown[sym] > 0:
                adjusted[sym] = 0.0

        # 2. Detect fresh closes
        for sym, weight in current_weights.items():
            if weight != 0 and adjusted.get(sym, 0.0) == 0.0:
                if sym not in self._cooldown or self._cooldown[sym] == 0:
                    self._cooldown[sym] = self.cooldown_bars

        # 3. Decrement cooldowns
        for sym in list(self._cooldown.keys()):
            if self._cooldown[sym] > 0:
                self._cooldown[sym] -= 1
            if self._cooldown[sym] <= 0:
                self._cooldown.pop(sym)

        return adjusted

class ScalingRisk(RiskManagementModel):
    def __init__(self, step_pct: float = 0.05, max_entries: int = 3, 
                 scale_increment: float = 0.25, cooldown_bars: int = 1):
        self.step_pct = step_pct
        self.max_entries = max_entries
        self.scale_increment = scale_increment
        self.cooldown_bars = cooldown_bars
        self._entries: dict[str, int] = {}
        self._cooldown: dict[str, int] = {}

    def evaluate(self, targets: dict[str, float], state: dict) -> dict[str, float]:
        adjusted = targets.copy()
        prices = state.get('prices', {})
        entry_prices = state.get('entry_prices', {})

        for sym, weight in adjusted.items():
            if weight <= 0:
                self._entries.pop(sym, None)
                continue

            price = prices.get(sym)
            entry = entry_prices.get(sym)
            if price is None or entry is None or entry <= 0:
                continue

            ret = (price / entry) - 1
            n = self._entries.get(sym, 0)

            if n < self.max_entries and self._cooldown.get(sym, 0) == 0:
                if ret >= self.step_pct * (n + 1):
                    adjusted[sym] = weight * (1 + self.scale_increment)
                    self._entries[sym] = n + 1
                    self._cooldown[sym] = self.cooldown_bars

        # Decrement cooldowns
        for sym in list(self._cooldown.keys()):
            if self._cooldown[sym] > 0:
                self._cooldown[sym] -= 1
            if self._cooldown[sym] <= 0:
                self._cooldown.pop(sym)

        return adjusted
