import logging
from datetime import timedelta

from orb_bot.config.constants import FLATTEN_MINUTES_BEFORE_CLOSE, FLATTEN_RETRY_SECONDS
from orb_bot.domain.ports import BrokerPort, Clock
from orb_bot.domain.types import TradingDay
from orb_bot.infra.notifier import Notifier

logger = logging.getLogger(__name__)


class FlattenService:
    def __init__(self, broker: BrokerPort, notifier: Notifier, clock: Clock) -> None:
        self._broker = broker
        self._notifier = notifier
        self._clock = clock

    def run(self, day: TradingDay) -> None:
        if self._clock.now() >= day.closes_at:
            # Market orders now would queue for tomorrow's open; the next session cleans up instead.
            return
        self._clock.sleep_until(day.closes_at - timedelta(minutes=FLATTEN_MINUTES_BEFORE_CLOSE))
        retry = timedelta(seconds=FLATTEN_RETRY_SECONDS)
        while True:
            try:
                self._flatten_once()
                return
            except Exception:
                logger.exception("flatten failed")
                if self._clock.now() + retry >= day.closes_at:
                    self._notifier.send(
                        "ORB bot: FALHA ao zerar", "posição pode ter ficado aberta — confira agora"
                    )
                    raise
                self._clock.sleep_until(self._clock.now() + retry)

    def _flatten_once(self) -> None:
        symbols = self._broker.open_position_symbols()
        if not symbols:
            return
        self._broker.close_everything()
        self._notifier.send("ORB bot: zerado antes do fechamento", ", ".join(symbols))
