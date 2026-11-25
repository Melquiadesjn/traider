from datetime import timedelta

from conftest import SESSION_OPEN, make_bar

from orb_bot.domain.strategy import build_opening_range, find_breakout, gap_ok

LATE = SESSION_OPEN + timedelta(hours=1)


def test_opening_range_uses_first_15_minutes(opening_bars):
    later = make_bar(15, high=200.0, low=1.0, close=150.0)
    opening_range = build_opening_range([*opening_bars, later], SESSION_OPEN)
    assert opening_range is not None
    assert (opening_range.high, opening_range.low) == (101.5, 99.0)


def test_opening_range_needs_every_bar(opening_bars):
    assert build_opening_range(opening_bars[:2], SESSION_OPEN) is None


def test_gap_filter(opening_bars):
    opening_range = build_opening_range(opening_bars, SESSION_OPEN)
    assert gap_ok(opening_range, previous_close=99.5)
    assert not gap_ok(opening_range, previous_close=95.0)


def test_breakout_requires_close_above_high(opening_bars):
    wick_only = make_bar(15, high=102.0, low=100.5, close=101.5, volume=5000)
    closes_above = make_bar(20, high=102.5, low=101.0, close=102.0, volume=5000)
    bars = [*opening_bars, wick_only, closes_above]
    signal = find_breakout("AAPL", bars, build_opening_range(bars, SESSION_OPEN), LATE)
    assert signal is not None
    assert signal.entry == 102.0
    assert signal.stop == 99.0
    assert signal.target == 102.0 + 2 * 3.0
    assert signal.triggered_at == SESSION_OPEN + timedelta(minutes=25)


def test_breakout_ignores_unfinished_bar(opening_bars):
    forming = make_bar(15, high=103.0, low=101.0, close=102.5, volume=5000)
    bars = [*opening_bars, forming]
    mid_bar = SESSION_OPEN + timedelta(minutes=17)
    assert find_breakout("AAPL", bars, build_opening_range(bars, SESSION_OPEN), mid_bar) is None


def test_breakout_needs_volume(opening_bars):
    weak = make_bar(15, high=103.0, low=101.0, close=102.5, volume=10)
    bars = [*opening_bars, weak]
    assert find_breakout("AAPL", bars, build_opening_range(bars, SESSION_OPEN), LATE) is None


def test_no_entries_after_window(opening_bars):
    after_window = make_bar(95, high=103.0, low=101.0, close=102.5, volume=5000)
    bars = [*opening_bars, after_window]
    end_of_day = SESSION_OPEN + timedelta(hours=6)
    opening_range = build_opening_range(bars, SESSION_OPEN)
    assert find_breakout("AAPL", bars, opening_range, end_of_day) is None
