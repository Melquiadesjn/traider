"""End-to-end trading day on a fake clock: session → flatten → journal with the real SimBroker."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from conftest import SESSION_OPEN, make_bar

from orb_bot import cli
from orb_bot.config.settings import Settings
from orb_bot.domain.types import TradingDay
from orb_bot.errors import MarketDataError
from orb_bot.infra.markdown_writer import MarkdownWriter
from orb_bot.infra.notifier import Notifier
from orb_bot.infra.sim_broker import SimBroker
from orb_bot.infra.state_store import StateStore
from orb_bot.services.flatten_service import FlattenService
from orb_bot.services.journal_service import JournalService
from orb_bot.services.session_service import SessionService

DAY = TradingDay(opens_at=SESSION_OPEN, closes_at=SESSION_OPEN.replace(hour=16, minute=0))


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def sleep_until(self, moment: datetime) -> None:
        self.current = max(self.current, moment)


class FakeData:
    """Serves only bars that have closed by the fake clock, like a live feed would."""

    def __init__(self, clock: FakeClock, bars, fail_first_previous: bool = False) -> None:
        self.clock = clock
        self.bars = bars
        self.fail_previous = fail_first_previous

    def intraday_bars(self, symbols, start, end=None):
        return {s: [b for b in self.bars if b.start >= start and b.end <= self.clock.now()]
                for s in symbols}

    def daily_closes(self, symbols, start, end):
        return {}

    def previous_closes(self, symbols, day):
        if self.fail_previous:
            self.fail_previous = False
            raise MarketDataError("Yahoo indisponível")
        return {s: 100.0 for s in symbols}


def _day_bars(spike: bool):
    bars = [make_bar(m, high=101.0, low=99.0, close=100.5, volume=1000) for m in (0, 5, 10)]
    bars.append(make_bar(15, high=101.8, low=100.8, close=101.5, volume=5000))
    for minute in range(20, 390, 5):
        if spike and minute == 150:
            bars.append(make_bar(minute, high=107.0, low=105.0, close=106.0, volume=3000))
        else:
            level = 106.0 if spike and minute > 150 else 101.6
            bars.append(make_bar(minute, high=level + 0.3, low=level - 0.3, close=level, volume=800))
    return bars


def _wire(tmp_path, spike=True, fail_first_previous=False, broker_cls=SimBroker, watchlist="AAPL"):
    clock = FakeClock(SESSION_OPEN - timedelta(minutes=30))
    data = FakeData(clock, _day_bars(spike), fail_first_previous)
    settings = Settings(_env_file=None, watchlist=watchlist, notifications_enabled=False)
    broker = broker_cls(data, clock, tmp_path / "sim.json", 10_000)
    state = StateStore(tmp_path / "state.json")
    notifier = Notifier(enabled=False)
    return SimpleNamespace(
        clock=clock,
        broker=broker,
        session=SessionService(settings, broker, data, state, notifier, clock),
        flatten=FlattenService(broker, notifier, clock),
        journal=JournalService(broker, state, MarkdownWriter(), notifier, logs_dir=tmp_path),
        state=state,
    )


def _sells(broker):
    return [f for f in broker.fills_since(SESSION_OPEN) if f.side == "sell"]


def test_full_day_hits_target_and_books_journal(tmp_path):
    bot = _wire(tmp_path)
    bot.session.run(DAY)
    trades = bot.state.trades_on("2026-10-21")
    assert [t["symbol"] for t in trades] == ["AAPL"]
    assert trades[0]["qty"] == 24  # capped at 25% of equity, not the 80 shares 2% risk allows
    bot.flatten.run(DAY)
    bot.journal.run(DAY)
    assert [(s.price, s.filled_at.time().isoformat()) for s in _sells(bot.broker)] == [(106.5, "12:05:00")]
    journal = (tmp_path / "2026-10-21.md").read_text()
    assert "AAPL" in journal and "+118.80" in journal
    assert bot.broker.account().last_equity == 10_000  # same day: prior mark is the start


def test_same_candle_signals_all_enter_up_to_the_daily_cap(tmp_path):
    bot = _wire(tmp_path, spike=False, watchlist="AAA,BBB,CCC,DDD")
    bot.session.run(DAY)
    trades = bot.state.trades_on("2026-10-21")
    assert [t["symbol"] for t in trades] == ["AAA", "BBB", "CCC"]
    # All three share one scan, so they fill at the same candle's price, not 5 minutes stale.
    assert {t["triggered_at"] for t in trades} == {trades[0]["triggered_at"]}
    assert all(t["qty"] == 24 for t in trades)
    assert sorted(bot.broker.open_position_symbols()) == ["AAA", "BBB", "CCC"]


def test_one_symbol_never_trades_twice_in_a_day(tmp_path):
    bot = _wire(tmp_path, spike=False, watchlist="AAA")
    bot.session.run(DAY)
    assert len(bot.state.trades_on("2026-10-21")) == 1


def test_yahoo_failure_before_first_scan_is_retried(tmp_path):
    bot = _wire(tmp_path, fail_first_previous=True)
    bot.session.run(DAY)
    assert len(bot.state.trades_on("2026-10-21")) == 1


def test_flatten_retries_after_a_failure(tmp_path):
    class FlakyOnce(SimBroker):
        armed = False

        def open_position_symbols(self):
            if FlakyOnce.armed:
                FlakyOnce.armed = False
                raise MarketDataError("timeout")
            return super().open_position_symbols()

    bot = _wire(tmp_path, spike=False, broker_cls=FlakyOnce)
    bot.session.run(DAY)
    FlakyOnce.armed = True
    bot.flatten.run(DAY)
    assert bot.broker.open_position_symbols() == []
    assert len(_sells(bot.broker)) == 1
    assert bot.clock.now() == DAY.closes_at - timedelta(minutes=5) + timedelta(seconds=20)


def test_failed_stale_cleanup_skips_trading_the_day(tmp_path):
    class BrokenAtOpen(SimBroker):
        def open_position_symbols(self):
            raise MarketDataError("timeout")

    bot = _wire(tmp_path, broker_cls=BrokenAtOpen)
    # Conservative on purpose: no new entries on top of positions the bot cannot see.
    with pytest.raises(MarketDataError):
        bot.session.run(DAY)
    assert bot.state.trades_on("2026-10-21") == []


def test_session_crash_still_flattens_and_journals(monkeypatch):
    calls = []

    def boom(day):
        raise RuntimeError("bug")

    container = SimpleNamespace(
        settings=Settings(_env_file=None, notifications_enabled=False),
        clock=SimpleNamespace(now=lambda: SESSION_OPEN),
        broker=SimpleNamespace(trading_day=lambda now: DAY),
        notifier=Notifier(enabled=False),
        session=SimpleNamespace(run=boom),
        flatten=SimpleNamespace(run=lambda day: calls.append("flatten")),
        journal=SimpleNamespace(run=lambda day: calls.append("journal")),
    )
    monkeypatch.setattr(cli, "build_container", lambda: container)
    assert cli._run_daily("run-day") == 1
    assert calls == ["flatten", "journal"]


@pytest.mark.parametrize("command,expected", [("flatten", ["flatten"]), ("journal", ["journal"])])
def test_single_stage_commands(monkeypatch, command, expected):
    calls = []
    container = SimpleNamespace(
        settings=Settings(_env_file=None),
        clock=SimpleNamespace(now=lambda: SESSION_OPEN),
        broker=SimpleNamespace(trading_day=lambda now: DAY),
        notifier=Notifier(enabled=False),
        session=SimpleNamespace(run=lambda day: calls.append("session")),
        flatten=SimpleNamespace(run=lambda day: calls.append("flatten")),
        journal=SimpleNamespace(run=lambda day: calls.append("journal")),
    )
    monkeypatch.setattr(cli, "build_container", lambda: container)
    assert cli._run_daily(command) == 0
    assert calls == expected
