import email.utils
import json
import logging
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from orb_bot.config.constants import (
    NEWS_TIMEOUT_SECONDS,
    SEC_FILINGS_URL,
    SEC_PAUSE_SECONDS,
    SEC_TICKERS_URL,
    YAHOO_RSS_URL,
    YAHOO_USER_AGENT,
)
from orb_bot.config.macro_events import SEC_8K_IMPORTANT_ITEMS
from orb_bot.domain.types import NewsItem, NewsResult
from orb_bot.errors import NewsError

logger = logging.getLogger(__name__)

_EXHIBITS_ITEM = "9.01"


class NewsFeeds:
    """Yahoo Finance headlines plus SEC 8-K filings. Read-only context: it never feeds a trade decision."""

    def __init__(self, sec_user_agent: str | None) -> None:
        self._sec_user_agent = sec_user_agent
        self._ciks: dict[str, str] | None = None

    def recent(self, symbols: list[str], since: datetime) -> NewsResult:
        items: list[NewsItem] = []
        warnings: list[str] = []
        for symbol in symbols:
            items += self._safely(symbol, warnings, self._headlines)
            if self._sec_user_agent:
                items += self._safely(symbol, warnings, self._filings)
        if not self._sec_user_agent:
            warnings.append("8-K da SEC desativado: defina SEC_USER_AGENT no .env")
        kept = sorted(
            (i for i in items if i.published_at >= since), key=lambda i: i.published_at, reverse=True
        )
        return NewsResult(items=kept, warnings=warnings)

    @staticmethod
    def _safely(symbol, warnings, fetch):
        try:
            return fetch(symbol)
        except NewsError as error:
            warnings.append(f"{symbol}: {error}")
            return []

    def _headlines(self, symbol: str) -> list[NewsItem]:
        return parse_rss(symbol, _get(YAHOO_RSS_URL.format(symbol=symbol), YAHOO_USER_AGENT))

    def _filings(self, symbol: str) -> list[NewsItem]:
        cik = self._cik_for(symbol)
        data = _get(SEC_FILINGS_URL.format(cik=cik), self._sec_user_agent or "")
        time.sleep(SEC_PAUSE_SECONDS)
        return parse_sec_atom(symbol, data)

    def _cik_for(self, symbol: str) -> str:
        if self._ciks is None:
            raw = json.loads(_get(SEC_TICKERS_URL, self._sec_user_agent or ""))
            self._ciks = {
                row["ticker"].upper().replace("-", "."): str(row["cik_str"]).zfill(10)
                for row in raw.values()
            }
        try:
            return self._ciks[symbol.upper().replace("-", ".")]
        except KeyError:
            raise NewsError("sem CIK na SEC") from None


def _get(url: str, user_agent: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=NEWS_TIMEOUT_SECONDS) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise NewsError(f"HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise NewsError(f"sem resposta ({type(error).__name__})") from error


def parse_time(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_rss(symbol: str, data: bytes) -> list[NewsItem]:
    root = _xml(symbol, data)
    items = []
    for node in root.iter("item"):
        published = parse_time(_text(node, "pubDate"))
        title = _text(node, "title")
        if published is None or not title:
            continue
        items.append(NewsItem(symbol, "Yahoo Finance", title, _text(node, "link"), published))
    return items


def parse_sec_atom(symbol: str, data: bytes) -> list[NewsItem]:
    root = _xml(symbol, data)
    company = next((_clean(e.text) for e in root.iter() if _local(e.tag) == "conformed-name"), symbol)
    items = []
    for entry in (e for e in root.iter() if _local(e.tag) == "entry"):
        published = parse_time(_text(entry, "updated"))
        if published is None:
            continue
        numbers = [n for n in re.findall(r"\d+\.\d+", _text(entry, "items-desc")) if n != _EXHIBITS_ITEM]
        flags = tuple(SEC_8K_IMPORTANT_ITEMS.get(n, f"item {n}") for n in numbers)
        link = next((e.get("href", "") for e in entry.iter() if _local(e.tag) == "link"), "")
        form = _text(entry, "filing-type") or "8-K"
        items.append(NewsItem(symbol, "SEC EDGAR", f"{company} entregou {form}", link, published, flags))
    return items


def _xml(symbol: str, data: bytes) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError as error:
        raise NewsError(f"feed inválido ({error})") from error


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean(text: str | None) -> str:
    return (text or "").strip()


def _text(node: ET.Element, name: str) -> str:
    return next((_clean(e.text) for e in node.iter() if _local(e.tag) == name), "")
