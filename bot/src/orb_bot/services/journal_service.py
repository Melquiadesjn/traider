from collections import defaultdict
from pathlib import Path

from orb_bot.config.constants import LOGS_DIR
from orb_bot.domain.ports import BrokerPort
from orb_bot.domain.types import Fill, TradingDay
from orb_bot.infra.markdown_writer import MarkdownWriter
from orb_bot.infra.notifier import Notifier
from orb_bot.infra.state_store import StateStore, TradeRecord
from orb_bot.services.context_service import DayContextService

_SKELETON = """# Journal — {day}

## Antes do pregão
- Humor: 1–10
- Sono: horas

## Fim do dia (preencher à noite)
- Aderência ao plano: /10
- Nota pessoal:
"""


class JournalService:
    def __init__(
        self,
        broker: BrokerPort,
        state: StateStore,
        writer: MarkdownWriter,
        notifier: Notifier,
        logs_dir: Path = LOGS_DIR,
        context: DayContextService | None = None,
    ) -> None:
        self._context = context
        self._logs_dir = logs_dir
        self._broker = broker
        self._state = state
        self._writer = writer
        self._notifier = notifier

    def run(self, day: TradingDay) -> None:
        today = day.opens_at.date().isoformat()
        fills = self._broker.fills_since(day.opens_at)
        trades = self._state.trades_on(today)
        pnl_by_symbol = _pnl_by_symbol(fills)
        # Also books the end-of-day equity mark the next session's daily-loss limit compares against.
        equity = self._broker.account().equity
        section = _render(trades, fills, pnl_by_symbol, equity)
        if self._context is not None:
            section += "\n\n" + self._context.render(day.opens_at.date(), day.opens_at, trades)
        path = self._logs_dir / f"{today}.md"
        self._writer.write_bot_section(path, section, _SKELETON.format(day=today))
        total = sum(pnl_by_symbol.values())
        self._notifier.send("ORB bot: journal do dia", f"{len(trades)} trade(s), P&L ${total:+.2f}")


def _pnl_by_symbol(fills: list[Fill]) -> dict[str, float]:
    pnl: dict[str, float] = defaultdict(float)
    for fill in fills:
        sign = -1 if fill.side == "buy" else 1
        pnl[fill.symbol] += sign * fill.qty * fill.price
    return dict(pnl)


def _render(
    trades: list[TradeRecord], fills: list[Fill], pnl: dict[str, float], equity: float
) -> str:
    lines = ["## Bot (automático)", ""]
    if not trades:
        lines.append("- Nenhum setup válido hoje. Ficar de fora também é seguir o plano.")
    for number, trade in enumerate(trades, start=1):
        symbol = trade["symbol"]
        exits = [f for f in fills if f.symbol == symbol and f.side == "sell"]
        exit_text = ", ".join(f"{f.filled_at:%H:%M} @ {f.price:.2f}" for f in exits) or "em aberto"
        risk = (trade["entry"] - trade["stop"]) * trade["qty"]
        lines += [
            f"### Trade #{number} — {symbol} (ORB long)",
            f"- Sinal: {trade['triggered_at'][11:16]} NY @ {trade['entry']:.2f} | qty {trade['qty']}",
            f"- Stop: {trade['stop']:.2f} (risco ${risk:.2f}) | Alvo: {trade['target']:.2f}",
            f"- Saída: {exit_text}",
            f"- P&L: ${pnl.get(symbol, 0.0):+.2f}",
            "",
        ]
    lines.append(f"**P&L do dia:** ${sum(pnl.values()):+.2f} | **Patrimônio:** ${equity:,.2f}")
    return "\n".join(lines)
