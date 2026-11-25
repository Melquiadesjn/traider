import logging
from dataclasses import dataclass

from orb_bot.config.constants import (
    BACKTEST_DATA_FEED,
    BOT_LOG_FILE,
    SIM_ACCOUNT_FILE,
    STATE_FILE,
)
from orb_bot.config.settings import Settings, get_settings
from orb_bot.domain.ports import BrokerPort, Clock, MarketDataPort
from orb_bot.infra.markdown_writer import MarkdownWriter
from orb_bot.infra.news_feeds import NewsFeeds
from orb_bot.infra.notifier import Notifier
from orb_bot.infra.sim_broker import SimBroker
from orb_bot.infra.state_store import StateStore
from orb_bot.infra.yahoo_market_data import YahooMarketData
from orb_bot.services.backtest_service import BacktestService
from orb_bot.services.clock import SystemClock
from orb_bot.services.context_service import DayContextService
from orb_bot.services.flatten_service import FlattenService
from orb_bot.services.journal_service import JournalService
from orb_bot.services.session_service import SessionService


@dataclass(frozen=True)
class Container:
    settings: Settings
    broker: BrokerPort
    clock: Clock
    notifier: Notifier
    session: SessionService
    flatten: FlattenService
    journal: JournalService


def configure_logging() -> None:
    BOT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(BOT_LOG_FILE)],
    )


def build_container() -> Container:
    settings = get_settings()
    clock = SystemClock()
    data = _market_data(settings)
    broker = _broker(settings, data, clock)
    state = StateStore(STATE_FILE)
    notifier = Notifier(settings.notifications_enabled)
    return Container(
        settings=settings,
        broker=broker,
        clock=clock,
        notifier=notifier,
        session=SessionService(settings, broker, data, state, notifier, clock),
        flatten=FlattenService(broker, notifier, clock),
        journal=JournalService(
            broker, state, MarkdownWriter(), notifier,
            context=DayContextService(NewsFeeds(settings.sec_user_agent)),
        ),
    )


def build_backtest() -> BacktestService:
    settings = get_settings()
    return BacktestService(_market_data(settings, BACKTEST_DATA_FEED), MarkdownWriter())


def _market_data(settings: Settings, alpaca_feed: str | None = None) -> MarketDataPort:
    if settings.broker == "alpaca":
        # Lazy import: alpaca-py is only needed when the Alpaca backend is selected.
        from orb_bot.infra.market_data import MarketDataRepository

        return MarketDataRepository(settings, alpaca_feed)
    return YahooMarketData()


def _broker(settings: Settings, data: MarketDataPort, clock: Clock) -> BrokerPort:
    if settings.broker == "alpaca":
        from orb_bot.infra.broker import BrokerRepository

        return BrokerRepository(settings)
    return SimBroker(data, clock, SIM_ACCOUNT_FILE, settings.sim_starting_cash)
