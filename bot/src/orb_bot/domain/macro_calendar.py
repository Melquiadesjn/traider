from datetime import date

from orb_bot.config.macro_events import (
    CPI_RELEASES,
    FOMC_MEETINGS,
    JOBS_RELEASES,
    MACRO_COVERAGE_END,
    MACRO_COVERAGE_START,
)
from orb_bot.errors import CalendarError


def macro_events_on(day: date) -> list[str]:
    if not date.fromisoformat(MACRO_COVERAGE_START) <= day <= date.fromisoformat(MACRO_COVERAGE_END):
        raise CalendarError(
            f"calendário macro cobre {MACRO_COVERAGE_START} a {MACRO_COVERAGE_END} "
            "(config/macro_events.py)"
        )
    key = day.isoformat()
    events = []
    for first_day, decision_day in FOMC_MEETINGS:
        if key == decision_day:
            events.append("FOMC: dia da decisão de juros (14h NY)")
        elif key == first_day:
            events.append("FOMC: 1º dia da reunião")
    if key in CPI_RELEASES:
        events.append("CPI (inflação) às 8h30 NY")
    if key in JOBS_RELEASES:
        events.append("Relatório de emprego (payroll) às 8h30 NY")
    return events
