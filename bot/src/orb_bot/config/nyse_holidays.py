# Source: https://www.nyse.com/markets/hours-calendars (read 2026-10).
# Extend before 2028 or the calendar refuses to answer.
NYSE_CALENDAR_YEARS = (2026, 2027)

NYSE_HOLIDAYS = frozenset({
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
})

# 1:00 p.m. New York closes
NYSE_EARLY_CLOSES = frozenset({"2026-11-27", "2026-12-24", "2027-11-26"})
