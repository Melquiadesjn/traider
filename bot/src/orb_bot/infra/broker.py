from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetCalendarRequest,
    GetOrdersRequest,
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

from orb_bot.config.constants import NY_TZ
from orb_bot.config.settings import Settings
from orb_bot.domain.types import AccountSnapshot, Fill, OrderPlan, TradingDay

_MAX_ORDERS_PER_QUERY = 500


class BrokerRepository:
    def __init__(self, settings: Settings) -> None:
        self._client = TradingClient(
            *settings.alpaca_credentials(),
            paper=True,
        )

    def trading_day(self, now: datetime) -> TradingDay | None:
        today = now.date()
        sessions = self._client.get_calendar(filters=GetCalendarRequest(start=today, end=today))
        session = next((s for s in sessions if s.date == today), None)
        if session is None:
            return None
        return TradingDay(opens_at=_as_ny(session.open), closes_at=_as_ny(session.close))

    def account(self) -> AccountSnapshot:
        account = self._client.get_account()
        return AccountSnapshot(
            equity=float(account.equity),
            last_equity=float(account.last_equity),
            buying_power=float(account.buying_power),
        )

    def submit_bracket(self, plan: OrderPlan) -> str:
        request = MarketOrderRequest(
            symbol=plan.signal.symbol,
            qty=plan.qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=plan.signal.target),
            stop_loss=StopLossRequest(stop_price=plan.signal.stop),
            client_order_id=plan.client_order_id,
        )
        return str(self._client.submit_order(order_data=request).id)

    def open_position_symbols(self) -> list[str]:
        return [p.symbol for p in self._client.get_all_positions()]

    def close_everything(self) -> None:
        self._client.close_all_positions(cancel_orders=True)

    def fills_since(self, since: datetime) -> list[Fill]:
        request = GetOrdersRequest(
            status=QueryOrderStatus.CLOSED, after=since, nested=True, limit=_MAX_ORDERS_PER_QUERY
        )
        orders = self._client.get_orders(filter=request)
        flat = [leg for order in orders for leg in [order, *(order.legs or [])]]
        return [
            Fill(
                symbol=o.symbol,
                side="buy" if o.side == OrderSide.BUY else "sell",
                qty=float(o.filled_qty),
                price=float(o.filled_avg_price),
                filled_at=o.filled_at.astimezone(NY_TZ),
            )
            for o in flat
            if o.filled_at and o.filled_avg_price and float(o.filled_qty or 0) > 0
        ]


def _as_ny(moment: datetime) -> datetime:
    # Alpaca's calendar returns naive New York wall-clock times.
    if moment.tzinfo is None:
        return moment.replace(tzinfo=NY_TZ)
    return moment.astimezone(NY_TZ)
