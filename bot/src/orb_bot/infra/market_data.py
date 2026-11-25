from datetime import date, datetime, time, timedelta

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from orb_bot.config.constants import BAR_MINUTES, NY_TZ
from orb_bot.config.settings import Settings
from orb_bot.domain.strategy import latest_closes
from orb_bot.domain.types import Bar

# Daily bars are fetched over calendar days; 10 covers weekends plus holidays.
_PREVIOUS_CLOSE_LOOKBACK_DAYS = 10


class MarketDataRepository:
    def __init__(self, settings: Settings, feed: str | None = None) -> None:
        self._client = StockHistoricalDataClient(
            *settings.alpaca_credentials(),
        )
        self._feed = DataFeed(feed or settings.data_feed)

    def intraday_bars(
        self, symbols: list[str], start: datetime, end: datetime | None = None
    ) -> dict[str, list[Bar]]:
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame(BAR_MINUTES, TimeFrameUnit.Minute),
            start=start,
            end=end,
            feed=self._feed,
        )
        return self._to_bars(self._client.get_stock_bars(request).data)

    def daily_closes(self, symbols: list[str], start: date, end: date) -> dict[str, dict[date, float]]:
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=datetime.combine(start, time.min, NY_TZ),
            end=datetime.combine(end, time.max, NY_TZ),
            feed=self._feed,
        )
        raw = self._client.get_stock_bars(request).data
        return {
            symbol: {b.timestamp.astimezone(NY_TZ).date(): float(b.close) for b in bars}
            for symbol, bars in raw.items()
        }

    def previous_closes(self, symbols: list[str], day: date) -> dict[str, float]:
        start = day - timedelta(days=_PREVIOUS_CLOSE_LOOKBACK_DAYS)
        return latest_closes(self.daily_closes(symbols, start, day - timedelta(days=1)))

    @staticmethod
    def _to_bars(raw: dict) -> dict[str, list[Bar]]:
        return {
            symbol: [
                Bar(
                    start=b.timestamp.astimezone(NY_TZ),
                    open=float(b.open),
                    high=float(b.high),
                    low=float(b.low),
                    close=float(b.close),
                    volume=float(b.volume),
                )
                for b in bars
            ]
            for symbol, bars in raw.items()
        }
