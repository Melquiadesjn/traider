from collections.abc import Sequence
from datetime import date, datetime, timedelta
from statistics import mean

from orb_bot.config.constants import (
    BAR_MINUTES,
    ENTRY_WINDOW_END,
    MAX_GAP_PCT,
    MIN_VOLUME_MULTIPLE,
    OPENING_RANGE_MINUTES,
    TARGET_R_MULTIPLE,
)
from orb_bot.domain.types import Bar, OpeningRange, Signal


def latest_closes(closes: dict[str, dict[date, float]]) -> dict[str, float]:
    return {symbol: by_day[max(by_day)] for symbol, by_day in closes.items() if by_day}


def regular_session(bars: Sequence[Bar], opens_at: datetime, closes_at: datetime) -> list[Bar]:
    return [b for b in bars if opens_at <= b.start < closes_at]


def build_opening_range(bars: Sequence[Bar], session_open: datetime) -> OpeningRange | None:
    ends_at = session_open + timedelta(minutes=OPENING_RANGE_MINUTES)
    range_bars = [b for b in bars if session_open <= b.start < ends_at]
    expected = OPENING_RANGE_MINUTES // BAR_MINUTES
    if len(range_bars) < expected:
        return None
    return OpeningRange(
        high=max(b.high for b in range_bars),
        low=min(b.low for b in range_bars),
        first_open=range_bars[0].open,
        ends_at=ends_at,
    )


def gap_ok(opening_range: OpeningRange, previous_close: float) -> bool:
    gap = abs(opening_range.first_open - previous_close) / previous_close
    return gap < MAX_GAP_PCT


def find_breakout(
    symbol: str,
    bars: Sequence[Bar],
    opening_range: OpeningRange,
    now: datetime,
) -> Signal | None:
    window_end = now.replace(
        hour=ENTRY_WINDOW_END.hour, minute=ENTRY_WINDOW_END.minute, second=0, microsecond=0
    )
    session_bars = [b for b in bars if b.start < opening_range.ends_at or b.end <= now]
    for index, bar in enumerate(session_bars):
        if bar.start < opening_range.ends_at or bar.end > window_end:
            continue
        if bar.close <= opening_range.high:
            continue
        if not _volume_confirms(bar, session_bars[:index]):
            continue
        return _signal_from(symbol, bar, opening_range)
    return None


def _volume_confirms(bar: Bar, earlier: Sequence[Bar]) -> bool:
    if not earlier:
        return False
    return bar.volume >= MIN_VOLUME_MULTIPLE * mean(b.volume for b in earlier)


def _signal_from(symbol: str, bar: Bar, opening_range: OpeningRange) -> Signal:
    entry = round(bar.close, 2)
    stop = round(opening_range.low, 2)
    target = round(entry + TARGET_R_MULTIPLE * (entry - stop), 2)
    return Signal(symbol=symbol, triggered_at=bar.end, entry=entry, stop=stop, target=target)

