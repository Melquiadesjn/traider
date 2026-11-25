from datetime import date, datetime, timedelta, timezone

import pytest
from conftest import SESSION_OPEN
from pydantic import ValidationError

from orb_bot.config.settings import Settings
from orb_bot.domain.macro_calendar import macro_events_on
from orb_bot.domain.types import NewsItem, NewsResult
from orb_bot.errors import CalendarError, NewsError
from orb_bot.infra import news_feeds
from orb_bot.infra.news_feeds import NewsFeeds, parse_rss, parse_sec_atom
from orb_bot.services.context_service import DayContextService

RSS = b"""<rss version="2.0"><channel>
<item><title>Apple launches new MacBook</title><link>https://finance.yahoo.com/a.html</link>
<pubDate>Tue, 27 Oct 2026 20:03:44 +0000</pubDate></item>
<item><title>Old story</title><link>https://finance.yahoo.com/b.html</link>
<pubDate>Mon, 19 Oct 2026 12:00:00 +0000</pubDate></item>
<item><title>Item without a date</title><link>https://finance.yahoo.com/c.html</link></item>
</channel></rss>"""

# Element names of EDGAR's company Atom feed.
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom">
<company-info><conformed-name>APPLE INC</conformed-name></company-info>
<entry><content type="text/xml"><accession-number>0000320193-26-000001</accession-number>
<filing-type>8-K</filing-type>
<items-desc>Item 2.02: Results of Operations Item 7.01: Reg FD Item 9.01: Exhibits</items-desc></content>
<link href="https://www.sec.gov/Archives/edgar/data/320193/x.htm"/>
<updated>2026-10-27T16:05:11-04:00</updated></entry></feed>"""

ENTRY_AT = SESSION_OPEN + timedelta(minutes=65)  # 10:35 NY
TRADE = {
    "symbol": "AAPL", "qty": 7, "entry": 345.55, "stop": 342.79, "target": 351.07,
    "triggered_at": ENTRY_AT.isoformat(), "client_order_id": "x", "order_id": "x",
}


def test_rss_parses_and_skips_items_without_date():
    items = parse_rss("AAPL", RSS)
    assert [i.title for i in items] == ["Apple launches new MacBook", "Old story"]
    assert items[0].published_at == datetime(2026, 10, 27, 20, 3, 44, tzinfo=timezone.utc)


def test_atom_flags_important_items_and_drops_exhibits():
    (item,) = parse_sec_atom("AAPL", ATOM)
    assert item.flags == ("resultados", "item 7.01")
    assert item.title == "APPLE INC entregou 8-K"
    assert item.published_at == datetime(2026, 10, 27, 20, 5, 11, tzinfo=timezone.utc)


def test_invalid_xml_raises_news_error():
    with pytest.raises(NewsError):
        parse_rss("AAPL", b"<html>blocked by proxy")


def test_recent_filters_by_time_and_warns_when_sec_is_off(monkeypatch):
    monkeypatch.setattr(news_feeds, "_get", lambda url, agent: RSS)
    since = datetime(2026, 10, 26, tzinfo=timezone.utc)
    result = NewsFeeds(sec_user_agent=None).recent(["AAPL"], since)
    assert [i.title for i in result.items] == ["Apple launches new MacBook"]
    assert any("SEC_USER_AGENT" in w for w in result.warnings)


def test_recent_keeps_going_when_one_symbol_fails(monkeypatch):
    def fake_get(url, agent):
        if "s=BAD" in url:
            raise NewsError("HTTP 404")
        return RSS

    monkeypatch.setattr(news_feeds, "_get", fake_get)
    result = NewsFeeds(None).recent(["BAD", "AAPL"], datetime(2026, 10, 26, tzinfo=timezone.utc))
    assert len(result.items) == 1
    assert any(w.startswith("BAD: HTTP 404") for w in result.warnings)


def test_macro_calendar_marks_fomc_cpi_and_payroll():
    assert macro_events_on(date(2026, 12, 8)) == ["FOMC: 1º dia da reunião"]
    assert "decisão" in macro_events_on(date(2026, 10, 28))[0]
    assert "CPI" in macro_events_on(date(2026, 11, 10))[0]
    assert "payroll" in macro_events_on(date(2026, 11, 6))[0]
    assert macro_events_on(date(2026, 11, 2)) == []


def test_macro_calendar_refuses_dates_it_does_not_cover():
    with pytest.raises(CalendarError):
        macro_events_on(date(2026, 10, 20))
    with pytest.raises(CalendarError):
        macro_events_on(date(2028, 1, 4))


class FakeNews:
    def __init__(self, items=None, boom=False):
        self.items, self.boom = items or [], boom

    def recent(self, symbols, since):
        if self.boom:
            raise RuntimeError("network down")
        return NewsResult(self.items, ["TSLA: HTTP 429"])


def _item(minutes_from_entry, flags=()):
    return NewsItem(
        "AAPL", "SEC EDGAR", "APPLE INC entregou 8-K", "https://sec.gov/x",
        ENTRY_AT + timedelta(minutes=minutes_from_entry), flags,
    )


def test_context_marks_news_before_and_after_entry():
    news = FakeNews([_item(-90, ("resultados",)), _item(30)])
    text = DayContextService(news).render(date(2026, 10, 21), SESSION_OPEN, [TRADE])
    assert "Calendário macro indisponível" in text  # 21/10 is before the covered range
    assert "antes da entrada" in text and "depois da entrada" in text
    assert "**[resultados]**" in text
    assert "Aviso: TSLA: HTTP 429" in text


def test_context_flags_the_macro_event_of_the_day():
    text = DayContextService(FakeNews()).render(date(2026, 10, 28), SESSION_OPEN, [TRADE])
    assert "**Evento macro:** FOMC: dia da decisão" in text
    assert "nenhuma manchete ou 8-K" in text


def test_context_survives_a_news_failure():
    text = DayContextService(FakeNews(boom=True)).render(date(2026, 10, 28), SESSION_OPEN, [TRADE])
    assert "Notícias indisponíveis: RuntimeError" in text


def test_context_without_trades_skips_the_network():
    text = DayContextService(FakeNews(boom=True)).render(date(2026, 10, 28), SESSION_OPEN, [])
    assert "Sem trades hoje" in text


def test_sec_user_agent_must_carry_a_contact():
    assert Settings(_env_file=None, sec_user_agent="").sec_user_agent is None
    assert Settings(_env_file=None, sec_user_agent="Ana ana@example.com").sec_user_agent
    with pytest.raises(ValidationError):
        Settings(_env_file=None, sec_user_agent="just-a-name")
