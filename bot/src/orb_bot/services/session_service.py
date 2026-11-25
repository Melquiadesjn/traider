import logging
from datetime import timedelta

from orb_bot.config.constants import (
    BAR_MINUTES,
    BAR_SETTLE_SECONDS,
    CLIENT_ORDER_PREFIX,
    ENTRY_WINDOW_END,
    MAX_TRADES_PER_DAY,
    OPENING_RANGE_MINUTES,
)
from orb_bot.config.settings import Settings
from orb_bot.domain.ports import BrokerPort, Clock, MarketDataPort
from orb_bot.domain.risk import check_limits, size_position
from orb_bot.domain.strategy import build_opening_range, find_breakout, gap_ok, regular_session
from orb_bot.domain.types import AccountSnapshot, Bar, OrderPlan, Signal, TradingDay
from orb_bot.infra.notifier import Notifier
from orb_bot.infra.state_store import StateStore
from orb_bot.services.clock import next_bar_check
from orb_bot.services.guards import halt_reason

logger = logging.getLogger(__name__)

# A breakout older than one bar means the bot was asleep; chasing it would
# fill far from the planned entry.
_MAX_SIGNAL_AGE = timedelta(minutes=BAR_MINUTES) + timedelta(seconds=BAR_SETTLE_SECONDS * 3)


class SessionService:
    def __init__(
        self,
        settings: Settings,
        broker: BrokerPort,
        data: MarketDataPort,
        state: StateStore,
        notifier: Notifier,
        clock: Clock,
    ) -> None:
        self._settings = settings
        self._broker = broker
        self._data = data
        self._state = state
        self._notifier = notifier
        self._clock = clock

    def run(self, day: TradingDay) -> None:
        self._close_stale_positions(day)
        range_ready = day.opens_at + timedelta(
            minutes=OPENING_RANGE_MINUTES, seconds=BAR_SETTLE_SECONDS
        )
        self._clock.sleep_until(range_ready)
        window_end = day.opens_at.replace(hour=ENTRY_WINDOW_END.hour, minute=ENTRY_WINDOW_END.minute)
        previous: dict[str, float] = {}

        while self._clock.now() < window_end:
            if reason := halt_reason(self._settings):
                self._notifier.send("ORB bot parado", reason)
                return
            try:
                if not previous:
                    previous = self._data.previous_closes(
                        self._settings.symbols, day.opens_at.date()
                    )
                if not self._scan_once(day, previous):
                    return
            except Exception:
                # Network/API hiccups must not end the session; the next bar retries.
                logger.exception("scan failed")
            self._clock.sleep_until(next_bar_check(self._clock.now(), day.opens_at))
        logger.info("entry window closed")

    def _scan_once(self, day: TradingDay, previous: dict[str, float]) -> bool:
        today = day.opens_at.date().isoformat()
        traded = {t["symbol"] for t in self._state.trades_on(today)}
        account = self._broker.account()
        week_key = "{}-W{:02d}".format(*day.opens_at.isocalendar()[:2])
        week_start = self._state.week_start_equity(week_key, account.last_equity)
        verdict = check_limits(account, week_start, len(traded))
        if not verdict.allowed:
            self._notifier.send("ORB bot: sem novas entradas hoje", verdict.reason)
            return False

        slots = MAX_TRADES_PER_DAY - len(traded)
        candidates = [s for s in self._settings.symbols if s not in traded and s in previous]
        bars = self._data.intraday_bars(candidates, day.opens_at)
        for symbol in candidates:
            if slots == 0:
                break
            session_bars = regular_session(bars.get(symbol, []), day.opens_at, day.closes_at)
            signal = self._signal_for(symbol, session_bars, day, previous[symbol])
            if signal and self._enter(today, signal, account):
                slots -= 1
                # Re-read so the next position is sized against the cash this one just used.
                account = self._broker.account()
        return True

    def _signal_for(
        self, symbol: str, bars: list[Bar], day: TradingDay, previous_close: float
    ) -> Signal | None:
        opening_range = build_opening_range(bars, day.opens_at)
        if opening_range is None or not gap_ok(opening_range, previous_close):
            return None
        now = self._clock.now()
        signal = find_breakout(symbol, bars, opening_range, now)
        if signal is None or now - signal.triggered_at > _MAX_SIGNAL_AGE:
            return None
        return signal

    def _enter(self, today: str, signal: Signal, account: AccountSnapshot) -> bool:
        qty = size_position(signal, account)
        if qty == 0:
            logger.info("%s: size 0 (risco/ação pequeno demais), ignorado", signal.symbol)
            return False
        plan = OrderPlan(signal, qty, f"{CLIENT_ORDER_PREFIX}-{today}-{signal.symbol}")
        order_id = self._broker.submit_bracket(plan)
        self._state.record_trade(today, plan, order_id)
        self._notifier.send(
            f"ORB bot: comprou {qty} {signal.symbol}",
            f"entrada ~{signal.entry} | stop {signal.stop} | alvo {signal.target}",
        )
        return True

    def _close_stale_positions(self, day: TradingDay) -> None:
        if self._clock.now() >= day.opens_at:
            return
        stale = self._broker.open_position_symbols()
        if stale:
            self._broker.close_everything()
            self._notifier.send("ORB bot: posição antiga zerada", ", ".join(stale))
