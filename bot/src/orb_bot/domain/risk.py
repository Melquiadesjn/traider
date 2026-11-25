import math

from orb_bot.config.constants import (
    MAX_DAILY_LOSS_PCT,
    MAX_POSITION_PCT,
    MAX_TRADES_PER_DAY,
    MAX_WEEKLY_LOSS_PCT,
    MIN_RISK_PER_SHARE,
    RISK_PER_TRADE_PCT,
)
from orb_bot.domain.types import AccountSnapshot, RiskVerdict, Signal


def size_position(signal: Signal, account: AccountSnapshot) -> int:
    if signal.risk_per_share < MIN_RISK_PER_SHARE:
        return 0
    by_risk = math.floor(account.equity * RISK_PER_TRADE_PCT / signal.risk_per_share)
    max_notional = min(account.equity * MAX_POSITION_PCT, account.buying_power)
    by_notional = math.floor(max_notional / signal.entry)
    return max(0, min(by_risk, by_notional))


def check_limits(
    account: AccountSnapshot,
    week_start_equity: float,
    trades_today: int,
) -> RiskVerdict:
    if trades_today >= MAX_TRADES_PER_DAY:
        return RiskVerdict(False, f"limite de {MAX_TRADES_PER_DAY} trade(s)/dia atingido")
    day_change = (account.equity - account.last_equity) / account.last_equity
    if day_change <= -MAX_DAILY_LOSS_PCT:
        return RiskVerdict(False, f"perda diária {day_change:.1%} atingiu o limite")
    week_change = (account.equity - week_start_equity) / week_start_equity
    if week_change <= -MAX_WEEKLY_LOSS_PCT:
        return RiskVerdict(False, f"perda semanal {week_change:.1%} atingiu o limite")
    return RiskVerdict(True, "ok")
