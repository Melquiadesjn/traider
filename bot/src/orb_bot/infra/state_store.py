import json
from pathlib import Path
from typing import TypedDict

from orb_bot.domain.types import OrderPlan


class TradeRecord(TypedDict):
    symbol: str
    qty: int
    entry: float
    stop: float
    target: float
    triggered_at: str
    client_order_id: str
    order_id: str


class StateStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def trades_on(self, day: str) -> list[TradeRecord]:
        return list(self._load().get("trades", {}).get(day, []))

    def record_trade(self, day: str, plan: OrderPlan, order_id: str) -> None:
        state = self._load()
        record: TradeRecord = {
            "symbol": plan.signal.symbol,
            "qty": plan.qty,
            "entry": plan.signal.entry,
            "stop": plan.signal.stop,
            "target": plan.signal.target,
            "triggered_at": plan.signal.triggered_at.isoformat(),
            "client_order_id": plan.client_order_id,
            "order_id": order_id,
        }
        state.setdefault("trades", {}).setdefault(day, []).append(record)
        self._save(state)

    def week_start_equity(self, week_key: str, current_equity: float) -> float:
        state = self._load()
        weeks = state.setdefault("week_start_equity", {})
        if week_key not in weeks:
            weeks[week_key] = current_equity
            self._save(state)
        return float(weeks[week_key])

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text())

    def _save(self, state: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(self._path)
