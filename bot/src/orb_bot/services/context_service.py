import logging
from datetime import date, datetime, timedelta

from orb_bot.config.constants import NEWS_LOOKBACK_HOURS, NEWS_MAX_ITEMS_PER_SYMBOL, NY_TZ
from orb_bot.domain.macro_calendar import macro_events_on
from orb_bot.domain.ports import NewsPort
from orb_bot.domain.types import NewsItem
from orb_bot.errors import CalendarError
from orb_bot.infra.state_store import TradeRecord

logger = logging.getLogger(__name__)


class DayContextService:
    """Writes what was happening around each trade. Context only: nothing here changes a decision."""

    def __init__(self, news: NewsPort | None) -> None:
        self._news = news

    def render(self, day: date, opens_at: datetime, trades: list[TradeRecord]) -> str:
        lines = ["### Contexto do dia (automático)", "", *self._macro_lines(day)]
        if trades and self._news is not None:
            lines += self._news_lines(opens_at, trades)
        elif not trades:
            lines.append("- Sem trades hoje, notícias não consultadas.")
        return "\n".join(lines)

    @staticmethod
    def _macro_lines(day: date) -> list[str]:
        try:
            events = macro_events_on(day)
        except CalendarError as error:
            return [f"- Calendário macro indisponível: {error}"]
        if not events:
            return ["- Sem FOMC, CPI ou payroll hoje."]
        return [f"- **Evento macro:** {event}" for event in events]

    def _news_lines(self, opens_at: datetime, trades: list[TradeRecord]) -> list[str]:
        symbols = list(dict.fromkeys(t["symbol"] for t in trades))
        since = opens_at - timedelta(hours=NEWS_LOOKBACK_HOURS)
        try:
            result = self._news.recent(symbols, since)  # type: ignore[union-attr]
        except Exception as error:
            logger.exception("news context failed")
            return [f"- Notícias indisponíveis: {type(error).__name__}"]
        lines = []
        for trade in trades:
            entry = datetime.fromisoformat(trade["triggered_at"])
            symbol_items = [i for i in result.items if i.symbol == trade["symbol"]]
            lines += _symbol_block(trade["symbol"], entry, symbol_items)
        lines += [f"- Aviso: {warning}" for warning in result.warnings]
        return lines


def _symbol_block(symbol: str, entry: datetime, items: list[NewsItem]) -> list[str]:
    if not items:
        return [f"- **{symbol}:** nenhuma manchete ou 8-K nas últimas {NEWS_LOOKBACK_HOURS}h."]
    lines = [f"- **{symbol}** (entrada {entry:%H:%M} NY):"]
    for item in items[:NEWS_MAX_ITEMS_PER_SYMBOL]:
        when = item.published_at.astimezone(NY_TZ)
        timing = "antes da entrada" if item.published_at < entry else "depois da entrada"
        flags = f" **[{', '.join(item.flags)}]**" if item.flags else ""
        lines.append(
            f"  - {when:%d/%m %H:%M} NY, {timing}, {item.source}: [{item.title}]({item.link}){flags}"
        )
    return lines
