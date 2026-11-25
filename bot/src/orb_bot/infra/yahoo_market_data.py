import json
import logging
import time as systime
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta
from urllib.parse import quote, urlencode

from orb_bot.config.constants import (
    NY_TZ,
    YAHOO_HOSTS,
    YAHOO_PAUSE_SECONDS,
    YAHOO_RETRY_BACKOFF_SECONDS,
    YAHOO_TIMEOUT_SECONDS,
    YAHOO_USER_AGENT,
)
from orb_bot.domain.strategy import latest_closes
from orb_bot.domain.types import Bar
from orb_bot.errors import MarketDataError

logger = logging.getLogger(__name__)

_TOO_MANY_REQUESTS = 429
_SERVER_ERROR = 500
_PREVIOUS_CLOSE_LOOKBACK_DAYS = 10


class YahooMarketData:
    def intraday_bars(
        self, symbols: list[str], start: datetime, end: datetime | None = None
    ) -> dict[str, list[Bar]]:
        stop = end or datetime.now(NY_TZ)
        return {s: self._bars(s, "5m", start, stop) for s in symbols}

    def daily_closes(
        self, symbols: list[str], start: date, end: date
    ) -> dict[str, dict[date, float]]:
        first = datetime.combine(start, time.min, NY_TZ)
        last = datetime.combine(end, time.max, NY_TZ)
        return {
            symbol: {b.start.date(): b.close for b in self._bars(symbol, "1d", first, last)}
            for symbol in symbols
        }

    def previous_closes(self, symbols: list[str], day: date) -> dict[str, float]:
        start = day - timedelta(days=_PREVIOUS_CLOSE_LOOKBACK_DAYS)
        return latest_closes(self.daily_closes(symbols, start, day - timedelta(days=1)))

    def _bars(self, symbol: str, interval: str, start: datetime, end: datetime) -> list[Bar]:
        params = urlencode({
            "interval": interval,
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
            "includePrePost": "false",
        })
        payload = self._get(f"/v8/finance/chart/{quote(symbol.replace('.', '-'))}?{params}")
        systime.sleep(YAHOO_PAUSE_SECONDS)
        return parse_chart(symbol, payload)

    def _get(self, path: str) -> dict:
        last_error: Exception | None = None
        for host in YAHOO_HOSTS:
            for attempt in range(2):
                request = urllib.request.Request(
                    f"https://{host}{path}", headers={"User-Agent": YAHOO_USER_AGENT}
                )
                try:
                    with urllib.request.urlopen(request, timeout=YAHOO_TIMEOUT_SECONDS) as response:
                        return json.loads(response.read())
                except urllib.error.HTTPError as error:
                    last_error = error
                    if error.code == _TOO_MANY_REQUESTS and attempt == 0:
                        systime.sleep(YAHOO_RETRY_BACKOFF_SECONDS)
                        continue
                    if error.code < _SERVER_ERROR and error.code != _TOO_MANY_REQUESTS:
                        # 4xx other than throttling is Yahoo's own answer (bad symbol, range).
                        return json.loads(error.read() or b"{}")
                    break
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                    last_error = error
                    break
        raise MarketDataError(f"Yahoo indisponível: {last_error}")


def parse_chart(symbol: str, payload: dict) -> list[Bar]:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise MarketDataError(f"{symbol}: {chart['error'].get('description', chart['error'])}")
    results = chart.get("result") or []
    if not results:
        return []
    result = results[0]
    stamps = result.get("timestamp") or []
    quote_ = (result.get("indicators", {}).get("quote") or [{}])[0]
    bars = []
    for i, stamp in enumerate(stamps):
        values = [quote_.get(k, [None] * len(stamps))[i] for k in ("open", "high", "low", "close")]
        if any(v is None for v in values):
            continue
        open_, high, low, close = (float(v) for v in values)
        volume = quote_.get("volume", [0] * len(stamps))[i] or 0
        bars.append(Bar(
            start=datetime.fromtimestamp(stamp, NY_TZ),
            open=open_, high=high, low=low, close=close, volume=float(volume),
        ))
    return bars
