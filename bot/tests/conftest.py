from datetime import datetime, timedelta

import pytest

from orb_bot.config.constants import NY_TZ
from orb_bot.domain.types import Bar

SESSION_OPEN = datetime(2026, 10, 21, 9, 30, tzinfo=NY_TZ)


def make_bar(minutes_after_open: int, high: float, low: float, close: float,
             volume: float = 1000, open_: float | None = None) -> Bar:
    return Bar(
        start=SESSION_OPEN + timedelta(minutes=minutes_after_open),
        open=open_ if open_ is not None else (high + low) / 2,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


@pytest.fixture
def opening_bars() -> list[Bar]:
    return [
        make_bar(0, high=101.0, low=99.0, close=100.5, open_=100.0),
        make_bar(5, high=101.5, low=99.5, close=101.0),
        make_bar(10, high=101.2, low=100.0, close=100.8),
    ]
