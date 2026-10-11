"""Circuit Breaker Engine — System-wide safety monitor.

Rules:
- Daily Drawdown Threshold: -3.0% of starting daily equity -> immediate emergency halt
- Consecutive Losses Threshold: 3 consecutive stop outs -> 24h trading cooldown
- On Breach: Triggers close_all_positions() via MT5 tools and suspends new orders

Acts as the hard boundary safety net for both Branch 1 (CSR) and Branch 2 (SMC).
"""

from datetime import UTC, datetime, timedelta

from src.core.logger import get_logger
from src.core.schemas import CircuitBreakerState
from src.tools.mt5_tools import close_all_positions

logger = get_logger("circuit_breaker")

_MAX_DAILY_DRAWDOWN_PCT = -3.0
_MAX_CONSECUTIVE_LOSSES = 3
_COOLDOWN_HOURS = 24


class CircuitBreaker:
    """Manages system-wide drawdowns and emergency halts."""

    def __init__(self, initial_daily_balance: float = 10000.0) -> None:
        self.initial_daily_balance = initial_daily_balance
        self.state = CircuitBreakerState(
            is_active=False,
            current_daily_drawdown_pct=0.0,
            consecutive_losses=0,
            cooldown_until=None,
            total_vetoes_today=0,
            halt_reason=None,
        )

    def check_equity(self, current_equity: float) -> CircuitBreakerState:
        """Check daily equity drawdown and trigger emergency halt if breached."""
        if self.initial_daily_balance <= 0:
            return self.state

        dd_pct = ((current_equity - self.initial_daily_balance) / self.initial_daily_balance) * 100.0
        self.state.current_daily_drawdown_pct = round(dd_pct, 2)

        now = datetime.now(UTC)
        # Check active cooldown period
        if self.state.cooldown_until and now < self.state.cooldown_until:
            self.state.is_active = True
            return self.state

        # Enforce -3% daily drawdown limit
        if dd_pct <= _MAX_DAILY_DRAWDOWN_PCT:
            self.state.is_active = True
            self.state.halt_reason = (
                f"Daily Drawdown breach: {dd_pct:.2f}% <= {_MAX_DAILY_DRAWDOWN_PCT}%. "
                f"Emergency halt triggered!"
            )
            self.state.cooldown_until = now + timedelta(hours=_COOLDOWN_HOURS)
            logger.critical(f"[CIRCUIT BREAKER TRIGGERED] {self.state.halt_reason}")
            close_all_positions()
            return self.state

        # Unlock system if drawdown recovered and cooldown expired
        if self.state.is_active and (not self.state.cooldown_until or now >= self.state.cooldown_until):
            logger.info("[CIRCUIT BREAKER] Cooldown period expired. System unlocked.")
            self.state.is_active = False
            self.state.halt_reason = None

        return self.state

    def record_loss(self) -> CircuitBreakerState:
        """Record consecutive stop out loss."""
        self.state.consecutive_losses += 1
        if self.state.consecutive_losses >= _MAX_CONSECUTIVE_LOSSES:
            self.state.is_active = True
            self.state.cooldown_until = datetime.now(UTC) + timedelta(hours=_COOLDOWN_HOURS)
            self.state.halt_reason = (
                f"{self.state.consecutive_losses} consecutive losses reached. "
                f"24h cooldown until {self.state.cooldown_until.isoformat()}"
            )
            logger.warning(f"[CIRCUIT BREAKER] {self.state.halt_reason}")
        return self.state

    def record_win(self) -> None:
        """Reset consecutive losses upon a winning trade."""
        self.state.consecutive_losses = 0

    def record_veto(self) -> None:
        """Increment count of vetoed orders for today."""
        self.state.total_vetoes_today += 1

    def reset_daily_baseline(self, new_daily_balance: float) -> None:
        """Reset starting daily equity baseline (runs at 00:00 UTC)."""
        self.initial_daily_balance = new_daily_balance
        self.state.current_daily_drawdown_pct = 0.0
        self.state.total_vetoes_today = 0
        now = datetime.now(UTC)
        if not self.state.cooldown_until or now >= self.state.cooldown_until:
            self.state.is_active = False
            self.state.halt_reason = None
        logger.info(f"[CIRCUIT BREAKER] Daily baseline reset to {new_daily_balance}")


circuit_breaker_instance = CircuitBreaker()
