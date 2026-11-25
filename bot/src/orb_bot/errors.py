class BotError(Exception):
    code = "bot_error"


class MarketDataError(BotError):
    code = "market_data_error"


class SimBrokerError(BotError):
    code = "sim_broker_error"


class CalendarError(BotError):
    code = "calendar_error"


class NewsError(BotError):
    code = "news_error"
