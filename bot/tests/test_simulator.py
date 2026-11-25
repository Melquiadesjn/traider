from datetime import timedelta

import pytest
from conftest import SESSION_OPEN, make_bar

from orb_bot.domain.simulator import simulate_bracket, summarize
from orb_bot.domain.types import Signal, TradeResult

SIGNAL = Signal("AAPL", SESSION_OPEN + timedelta(minutes=20), entry=102.0, stop=99.0, target=108.0)
FLATTEN = SESSION_OPEN + timedelta(hours=6, minutes=25)


def test_target_hit():
    bars = [make_bar(20, high=105, low=101, close=104), make_bar(25, high=109, low=104, close=108.5)]
    result = simulate_bracket(SIGNAL, bars, FLATTEN)
    assert (result.exit_reason, result.r_multiple) == ("target", 2.0)


def test_same_bar_counts_as_stop():
    bars = [make_bar(20, high=110, low=98, close=104)]
    assert simulate_bracket(SIGNAL, bars, FLATTEN).exit_reason == "stop"


def test_gap_through_stop_fills_at_open():
    bars = [make_bar(20, high=97.5, low=96, close=97, open_=97.0)]
    assert simulate_bracket(SIGNAL, bars, FLATTEN).r_multiple == pytest.approx(-5 / 3)


def test_flatten_at_last_bar():
    bars = [make_bar(20, high=104, low=101, close=103.5)]
    result = simulate_bracket(SIGNAL, bars, FLATTEN)
    assert result.exit_reason == "flatten"
    assert result.r_multiple == pytest.approx(0.5)


def test_summary_expectancy_and_drawdown():
    results = [TradeResult("X", "d", 0, 0, "", r) for r in (2.0, -1.0, -1.0, 2.0)]
    stats = summarize(results)
    assert stats.win_rate == 0.5
    assert stats.expectancy_r == 0.5
    assert stats.max_drawdown_r == -2.0


def test_cost_charges_two_sides_on_stop_one_on_target():
    from orb_bot.config.constants import SIM_SLIPPAGE_PCT

    per_side = SIM_SLIPPAGE_PCT * SIGNAL.entry / SIGNAL.risk_per_share
    stop = simulate_bracket(SIGNAL, [make_bar(20, high=110, low=98, close=104)], FLATTEN)
    target = simulate_bracket(SIGNAL, [make_bar(20, high=109, low=101, close=108)], FLATTEN)
    assert stop.cost_r == pytest.approx(2 * per_side)
    assert target.cost_r == pytest.approx(per_side)
    assert stop.net_r == pytest.approx(stop.r_multiple - 2 * per_side)


def test_random_benchmark_keeps_risk_and_sample_count():
    import random

    from orb_bot.domain.simulator import random_entry_benchmark

    window = [make_bar(20, high=103, low=101, close=102), make_bar(25, high=104, low=102, close=103)]
    session = [*window, make_bar(30, high=103.5, low=102.5, close=103)]
    twins = random_entry_benchmark(SIGNAL, window, session, FLATTEN, random.Random(1), samples=10)
    assert len(twins) == 10
    assert {t.entry for t in twins} <= {102.0, 103.0}
    # 1R must equal the original signal's risk: entry 103, flatten at 103 → 0R gross.
    assert all(t.r_multiple == pytest.approx(0.0) for t in twins if t.entry == 103.0)
