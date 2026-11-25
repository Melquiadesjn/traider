from datetime import date, datetime
from typing import Protocol

from orb_bot.domain.types import AccountSnapshot, Bar, Fill, NewsResult, OrderPlan, TradingDay


class Clock(Protocol):
    def now(self) -> datetime: ...

    def sleep_until(self, moment: datetime) -> None: ...


class MarketDataPort(Protocol):
    def intraday_bars(
        self, symbols: list[str], start: datetime, end: datetime | None = None
    ) -> dict[str, list[Bar]]: ...

    def daily_closes(
        self, symbols: list[str], start: date, end: date
    ) -> dict[str, dict[date, float]]: ...

    def previous_closes(self, symbols: list[str], day: date) -> dict[str, float]: ...


class BrokerPort(Protocol):
    def trading_day(self, now: datetime) -> TradingDay | None: ...

    def account(self) -> AccountSnapshot: ...

    def submit_bracket(self, plan: OrderPlan) -> str: ...

    def open_position_symbols(self) -> list[str]: ...

    def close_everything(self) -> None: ...

    def fills_since(self, since: datetime) -> list[Fill]: ...


class NewsPort(Protocol):
    def recent(self, symbols: list[str], since: datetime) -> NewsResult: ...
