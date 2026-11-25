import random
from collections.abc import Sequence
from datetime import datetime
from itertools import accumulate
from statistics import mean, stdev

from orb_bot.config.constants import SIM_SLIPPAGE_PCT, TARGET_R_MULTIPLE
from orb_bot.domain.types import BacktestStats, Bar, BracketExit, Signal, TradeResult


def find_bracket_exit(signal: Signal, bars: Sequence[Bar]) -> BracketExit | None:
    """First stop or target touched by bars after the signal.

    When one bar touches both we assume the stop hit first: 5-minute bars
    cannot tell the order, so fills stay pessimistic.
    """
    for bar in bars:
        if bar.start < signal.triggered_at:
            continue
        if bar.low <= signal.stop:
            return BracketExit(min(bar.open, signal.stop), "stop", bar.end)
        if bar.high >= signal.target:
            return BracketExit(max(bar.open, signal.target), "target", bar.end)
    return None


def simulate_bracket(signal: Signal, bars: Sequence[Bar], flatten_at: datetime) -> TradeResult:
    after = [b for b in bars if b.start >= signal.triggered_at and b.end <= flatten_at]
    exit_ = find_bracket_exit(signal, after)
    if exit_:
        return _result(signal, exit_.price, exit_.reason)
    last_price = after[-1].close if after else signal.entry
    return _result(signal, last_price, "flatten")


def random_entry_benchmark(
    signal: Signal,
    window_bars: Sequence[Bar],
    session: Sequence[Bar],
    flatten_at: datetime,
    rng: random.Random,
    samples: int,
) -> list[TradeResult]:
    """Same day, same risk per share and target multiple, long at random closed bars.

    If the breakout trigger carries information, the strategy should beat this.
    """
    if not window_bars:
        return []
    risk = signal.risk_per_share
    results = []
    for _ in range(samples):
        bar = rng.choice(window_bars)
        entry = round(bar.close, 2)
        twin = Signal(
            symbol=signal.symbol,
            triggered_at=bar.end,
            entry=entry,
            stop=round(entry - risk, 2),
            target=round(entry + TARGET_R_MULTIPLE * risk, 2),
        )
        results.append(simulate_bracket(twin, session, flatten_at))
    return results


def summarize(results: Sequence[TradeResult]) -> BacktestStats:
    if not results:
        return BacktestStats(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0)
    r_values = [r.net_r for r in results]
    wins = [r for r in r_values if r > 0]
    losses = [r for r in r_values if r <= 0]
    return BacktestStats(
        trades=len(r_values),
        wins=len(wins),
        win_rate=len(wins) / len(r_values),
        avg_win_r=mean(wins) if wins else 0.0,
        avg_loss_r=mean(losses) if losses else 0.0,
        expectancy_r=mean(r_values),
        max_drawdown_r=_max_drawdown(r_values),
        gross_expectancy_r=mean(r.r_multiple for r in results),
        std_error_r=stdev(r_values) / len(r_values) ** 0.5 if len(r_values) > 1 else 0.0,
    )


def _max_drawdown(r_values: Sequence[float]) -> float:
    peak = 0.0
    worst = 0.0
    for equity in accumulate(r_values):
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return worst


def _result(signal: Signal, exit_price: float, reason: str) -> TradeResult:
    # Market entry, stop and flatten pay slippage; a limit target fills at its price.
    slipped_sides = 1 if reason == "target" else 2
    return TradeResult(
        symbol=signal.symbol,
        day=signal.triggered_at.date().isoformat(),
        entry=signal.entry,
        exit=round(exit_price, 2),
        exit_reason=reason,
        r_multiple=(exit_price - signal.entry) / signal.risk_per_share,
        cost_r=slipped_sides * SIM_SLIPPAGE_PCT * signal.entry / signal.risk_per_share,
    )
