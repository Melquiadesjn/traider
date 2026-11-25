from dataclasses import dataclass
from datetime import datetime, timedelta

from orb_bot.config.constants import BAR_MINUTES


@dataclass(frozen=True)
class Bar:
    start: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=BAR_MINUTES)


@dataclass(frozen=True)
class OpeningRange:
    high: float
    low: float
    first_open: float
    ends_at: datetime


@dataclass(frozen=True)
class Signal:
    symbol: str
    triggered_at: datetime
    entry: float
    stop: float
    target: float

    @property
    def risk_per_share(self) -> float:
        return self.entry - self.stop


@dataclass(frozen=True)
class OrderPlan:
    signal: Signal
    qty: int
    client_order_id: str


@dataclass(frozen=True)
class RiskVerdict:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class TradingDay:
    opens_at: datetime
    closes_at: datetime


@dataclass(frozen=True)
class AccountSnapshot:
    equity: float
    last_equity: float
    buying_power: float


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: str
    qty: float
    price: float
    filled_at: datetime


@dataclass(frozen=True)
class BracketExit:
    price: float
    reason: str
    at: datetime


@dataclass(frozen=True)
class TradeResult:
    symbol: str
    day: str
    entry: float
    exit: float
    exit_reason: str
    r_multiple: float
    cost_r: float = 0.0

    @property
    def net_r(self) -> float:
        return self.r_multiple - self.cost_r


@dataclass(frozen=True)
class BacktestStats:
    trades: int
    wins: int
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    expectancy_r: float
    max_drawdown_r: float
    gross_expectancy_r: float = 0.0
    std_error_r: float = 0.0


@dataclass(frozen=True)
class NewsItem:
    symbol: str
    source: str
    title: str
    link: str
    published_at: datetime
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class NewsResult:
    items: list[NewsItem]
    warnings: list[str]
