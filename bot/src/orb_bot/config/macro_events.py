# Source, read 2026-10-28:
#   FOMC  https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (dates are tentative until confirmed)
#   CPI   https://www.bls.gov/schedule/news_release/cpi.htm   (08:30 ET)
#   Jobs  https://www.bls.gov/schedule/news_release/empsit.htm (08:30 ET)
# BLS pages only list releases from the 2026-10 reference month on, so coverage starts here.
MACRO_COVERAGE_START = "2026-10-28"
MACRO_COVERAGE_END = "2027-12-31"

# (first day, decision day) of each two-day meeting
FOMC_MEETINGS = (
    ("2026-10-27", "2026-10-28"), ("2026-12-08", "2026-12-09"),
    ("2027-01-26", "2027-01-27"), ("2027-03-16", "2027-03-17"),
    ("2027-04-27", "2027-04-28"), ("2027-06-08", "2027-06-09"),
    ("2027-07-27", "2027-07-28"), ("2027-09-14", "2027-09-15"),
    ("2027-10-26", "2027-10-27"), ("2027-12-07", "2027-12-08"),
)

CPI_RELEASES = frozenset({
    "2026-11-10", "2026-12-10", "2027-01-13", "2027-02-11", "2027-03-10", "2027-04-13",
    "2027-05-12", "2027-06-10", "2027-07-14", "2027-08-11", "2027-09-14", "2027-10-14",
    "2027-11-10", "2027-12-10",
})

JOBS_RELEASES = frozenset({
    "2026-11-06", "2026-12-04", "2027-01-08", "2027-02-05", "2027-03-05", "2027-04-02",
    "2027-05-07", "2027-06-04", "2027-07-02", "2027-08-06", "2027-09-03", "2027-10-08",
    "2027-11-05", "2027-12-03",
})

# Standard 8-K item numbers; others are shown as "item X.XX".
SEC_8K_IMPORTANT_ITEMS = {
    "1.03": "falência",
    "1.05": "incidente cibernético",
    "2.02": "resultados",
    "2.06": "impairment",
    "3.01": "aviso de delisting",
    "4.02": "demonstrações financeiras não confiáveis",
    "5.02": "mudança de diretoria",
}
