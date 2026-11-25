import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from orb_bot.config.constants import SIM_SLIPPAGE_PCT
from orb_bot.domain.nyse_calendar import trading_day
from orb_bot.domain.ports import Clock, MarketDataPort
from orb_bot.domain.simulator import find_bracket_exit
from orb_bot.domain.types import AccountSnapshot, Fill, OrderPlan, Signal, TradingDay
from orb_bot.errors import SimBrokerError


class SimPosition(TypedDict):
    qty: int
    entry: float
    stop: float
    target: float
    opened_at: str


class SimFill(TypedDict):
    symbol: str
    side: str
    qty: float
    price: float
    filled_at: str


class SimAccount(TypedDict):
    cash: float
    positions: dict[str, SimPosition]
    fills: list[SimFill]
    order_ids: list[str]
    equity_marks: dict[str, float]


class SimBroker:
    """Paper broker kept in a local JSON file.

    Stop and target are evaluated lazily against real bars whenever the
    account is touched, so a stop hit at 13:00 is booked at 13:00 even if the
    bot only looks again at the 15:55 flatten.
    """

    def __init__(
        self, data: MarketDataPort, clock: Clock, path: Path, starting_cash: float
    ) -> None:
        self._data = data
        self._clock = clock
        self._path = path
        self._starting_cash = starting_cash

    def trading_day(self, now: datetime) -> TradingDay | None:
        return trading_day(now.date())

    def account(self) -> AccountSnapshot:
        state, marks = self._synced()
        equity = state["cash"] + sum(p["qty"] * marks[s] for s, p in state["positions"].items())
        today = self._clock.now().date().isoformat()
        prior = [d for d in state["equity_marks"] if d < today]
        last_equity = state["equity_marks"][max(prior)] if prior else self._starting_cash
        state["equity_marks"][today] = round(equity, 2)
        self._save(state)
        return AccountSnapshot(equity=equity, last_equity=last_equity, buying_power=state["cash"])

    def submit_bracket(self, plan: OrderPlan) -> str:
        state, _ = self._synced()
        symbol = plan.signal.symbol
        if plan.client_order_id in state["order_ids"]:
            raise SimBrokerError(f"ordem duplicada {plan.client_order_id}")
        if symbol in state["positions"]:
            raise SimBrokerError(f"já existe posição em {symbol}")
        price = round(plan.signal.entry * (1 + SIM_SLIPPAGE_PCT), 2)
        cost = price * plan.qty
        if cost > state["cash"]:
            raise SimBrokerError(f"saldo insuficiente: ${cost:.2f} > ${state['cash']:.2f}")
        now = self._clock.now()
        state["cash"] -= cost
        state["positions"][symbol] = {
            "qty": plan.qty, "entry": price, "stop": plan.signal.stop,
            "target": plan.signal.target, "opened_at": plan.signal.triggered_at.isoformat(),
        }
        state["order_ids"].append(plan.client_order_id)
        self._record_fill(state, symbol, "buy", plan.qty, price, now)
        self._save(state)
        return plan.client_order_id

    def open_position_symbols(self) -> list[str]:
        state, _ = self._synced()
        return list(state["positions"])

    def close_everything(self) -> None:
        state, marks = self._synced()
        now = self._clock.now()
        for symbol in list(state["positions"]):
            price = round(marks[symbol] * (1 - SIM_SLIPPAGE_PCT), 2)
            self._close(state, symbol, price, now)
        self._save(state)

    def fills_since(self, since: datetime) -> list[Fill]:
        state, _ = self._synced()
        return [
            Fill(f["symbol"], f["side"], f["qty"], f["price"], datetime.fromisoformat(f["filled_at"]))
            for f in state["fills"]
            if datetime.fromisoformat(f["filled_at"]) >= since
        ]

    def _synced(self) -> tuple[SimAccount, dict[str, float]]:
        state = self._load()
        now = self._clock.now()
        marks: dict[str, float] = {}
        for symbol, position in list(state["positions"].items()):
            opened_at = datetime.fromisoformat(position["opened_at"])
            bars = self._data.intraday_bars([symbol], opened_at).get(symbol, [])
            closed = [b for b in bars if b.end <= now]
            signal = Signal(symbol, opened_at, position["entry"], position["stop"], position["target"])
            exit_ = find_bracket_exit(signal, closed)
            if exit_:
                slip = SIM_SLIPPAGE_PCT if exit_.reason == "stop" else 0.0
                self._close(state, symbol, round(exit_.price * (1 - slip), 2), exit_.at)
                continue
            marks[symbol] = bars[-1].close if bars else position["entry"]
        self._save(state)
        return state, marks

    def _close(self, state: SimAccount, symbol: str, price: float, at: datetime) -> None:
        position = state["positions"].pop(symbol)
        state["cash"] += price * position["qty"]
        self._record_fill(state, symbol, "sell", position["qty"], price, at)

    @staticmethod
    def _record_fill(
        state: SimAccount, symbol: str, side: str, qty: float, price: float, at: datetime
    ) -> None:
        state["fills"].append({
            "symbol": symbol, "side": side, "qty": qty, "price": price,
            "filled_at": at.isoformat(),
        })

    def _load(self) -> SimAccount:
        if not self._path.exists():
            return {"cash": self._starting_cash, "positions": {}, "fills": [],
                    "order_ids": [], "equity_marks": {}}
        return json.loads(self._path.read_text())

    def _save(self, state: SimAccount) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(self._path)
