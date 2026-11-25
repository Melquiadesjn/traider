from datetime import date, datetime, timedelta

import pytest
from conftest import SESSION_OPEN, make_bar

from orb_bot.config.constants import SIM_SLIPPAGE_PCT
from orb_bot.domain.nyse_calendar import trading_day
from orb_bot.domain.types import Bar, OrderPlan, Signal
from orb_bot.errors import CalendarError, SimBrokerError
from orb_bot.infra.sim_broker import SimBroker
from orb_bot.infra.yahoo_market_data import parse_chart

SIGNAL = Signal("AAPL", SESSION_OPEN + timedelta(minutes=20), entry=102.0, stop=99.0, target=108.0)
PLAN = OrderPlan(SIGNAL, qty=10, client_order_id="orb-test-AAPL")


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def sleep_until(self, moment: datetime) -> None:
        self.current = max(self.current, moment)


class FakeData:
    def __init__(self, bars: list[Bar]) -> None:
        self.bars = bars

    def intraday_bars(self, symbols, start, end=None):
        return {s: [b for b in self.bars if b.start >= start] for s in symbols}

    def daily_closes(self, symbols, start, end):
        return {}

    def previous_closes(self, symbols, day):
        return {}


def _broker(tmp_path, bars, minutes_after_open=25):
    clock = FakeClock(SESSION_OPEN + timedelta(minutes=minutes_after_open))
    return SimBroker(FakeData(bars), clock, tmp_path / "sim.json", 10_000), clock


def test_entry_debits_cash_with_slippage(tmp_path):
    broker, _ = _broker(tmp_path, [make_bar(20, high=103, low=101, close=102.5)])
    broker.submit_bracket(PLAN)
    fill_price = round(102.0 * (1 + SIM_SLIPPAGE_PCT), 2)
    account = broker.account()
    assert account.buying_power == pytest.approx(10_000 - 10 * fill_price)
    assert account.equity == pytest.approx(account.buying_power + 10 * 102.5)
    assert broker.open_position_symbols() == ["AAPL"]


def test_target_booked_at_bar_time(tmp_path):
    bars = [make_bar(20, high=103, low=101, close=102.5), make_bar(60, high=109, low=105, close=108.5)]
    broker, clock = _broker(tmp_path, bars)
    broker.submit_bracket(PLAN)
    clock.current = SESSION_OPEN + timedelta(hours=6)
    assert broker.open_position_symbols() == []
    sell = [f for f in broker.fills_since(SESSION_OPEN) if f.side == "sell"][0]
    assert sell.price == 108.0
    assert sell.filled_at == SESSION_OPEN + timedelta(minutes=65)


def test_unfinished_bar_does_not_trigger_stop(tmp_path):
    broker, _ = _broker(tmp_path, [make_bar(20, high=103, low=98, close=100)], minutes_after_open=22)
    broker.submit_bracket(PLAN)
    assert broker.open_position_symbols() == ["AAPL"]


def test_close_everything_sells_at_last_price(tmp_path):
    broker, _ = _broker(tmp_path, [make_bar(20, high=104, low=101, close=103.0)])
    broker.submit_bracket(PLAN)
    broker.close_everything()
    sell = [f for f in broker.fills_since(SESSION_OPEN) if f.side == "sell"][0]
    assert sell.price == round(103.0 * (1 - SIM_SLIPPAGE_PCT), 2)


def test_duplicate_order_rejected(tmp_path):
    broker, _ = _broker(tmp_path, [])
    broker.submit_bracket(PLAN)
    with pytest.raises(SimBrokerError):
        broker.submit_bracket(PLAN)


def test_nyse_calendar():
    assert trading_day(date(2026, 10, 24)) is None  # Saturday
    assert trading_day(date(2026, 11, 26)) is None  # Thanksgiving
    assert trading_day(date(2026, 11, 27)).closes_at.hour == 13
    assert trading_day(date(2026, 10, 23)).opens_at.hour == 9
    with pytest.raises(CalendarError):
        trading_day(date(2028, 1, 3))


def test_parse_yahoo_chart_skips_null_bars():
    payload = {"chart": {"error": None, "result": [{
        "timestamp": [1792762200, 1792762500],
        "indicators": {"quote": [{
            "open": [100.0, None], "high": [101.0, None], "low": [99.0, None],
            "close": [100.5, None], "volume": [1000, None],
        }]},
    }]}}
    bars = parse_chart("AAPL", payload)
    assert len(bars) == 1
    assert bars[0].close == 100.5
    assert bars[0].start.tzinfo is not None
