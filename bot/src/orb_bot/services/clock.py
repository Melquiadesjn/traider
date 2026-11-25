import time
from datetime import datetime, timedelta

from orb_bot.config.constants import BAR_MINUTES, BAR_SETTLE_SECONDS, NY_TZ

# Sleeping in short chunks keeps the process responsive after a laptop wakes up.
_MAX_SLEEP_CHUNK_SECONDS = 30


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(NY_TZ)

    def sleep_until(self, moment: datetime) -> None:
        while (remaining := (moment - self.now()).total_seconds()) > 0:
            time.sleep(min(remaining, _MAX_SLEEP_CHUNK_SECONDS))


def next_bar_check(now: datetime, session_open: datetime) -> datetime:
    elapsed = (now - session_open).total_seconds()
    bar_seconds = BAR_MINUTES * 60
    bars_done = int(elapsed // bar_seconds) + 1
    return session_open + timedelta(seconds=bars_done * bar_seconds + BAR_SETTLE_SECONDS)
