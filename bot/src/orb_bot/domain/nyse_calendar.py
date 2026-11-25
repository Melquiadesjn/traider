from datetime import date, datetime, time

from orb_bot.config.constants import DEFAULT_MARKET_OPEN, EARLY_CLOSE, NY_TZ, REGULAR_CLOSE
from orb_bot.config.nyse_holidays import NYSE_CALENDAR_YEARS, NYSE_EARLY_CLOSES, NYSE_HOLIDAYS
from orb_bot.domain.types import TradingDay
from orb_bot.errors import CalendarError

_SATURDAY = 5


def trading_day(day: date) -> TradingDay | None:
    if day.year not in NYSE_CALENDAR_YEARS:
        raise CalendarError(f"feriados da NYSE de {day.year} não cadastrados (config/nyse_holidays.py)")
    if day.weekday() >= _SATURDAY or day.isoformat() in NYSE_HOLIDAYS:
        return None
    close = EARLY_CLOSE if day.isoformat() in NYSE_EARLY_CLOSES else REGULAR_CLOSE
    return TradingDay(opens_at=_at(day, DEFAULT_MARKET_OPEN), closes_at=_at(day, close))


def _at(day: date, moment: time) -> datetime:
    return datetime.combine(day, moment, NY_TZ)
