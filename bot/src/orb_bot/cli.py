import argparse
import logging
import sys
from collections.abc import Callable
from datetime import date, timedelta

from pydantic import ValidationError

from orb_bot.app import Container, build_backtest, build_container, configure_logging
from orb_bot.config.constants import ALPACA_BACKTEST_DAYS, YAHOO_BACKTEST_DAYS
from orb_bot.config.settings import ENV_FILE, get_settings
from orb_bot.domain.types import TradingDay
from orb_bot.services.guards import halt_reason

logger = logging.getLogger("orb_bot")



def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    configure_logging()
    try:
        get_settings()
    except ValidationError as error:
        logger.error("configuração inválida em %s:\n%s", ENV_FILE, error)
        return 2
    if args.command == "backtest":
        return _backtest(args)
    if args.command == "status":
        return _status()
    return _run_daily(args.command)


def _run_daily(command: str) -> int:
    container = build_container()
    day = _trading_day(container)
    if day is None:
        return 0
    stages: list[tuple[str, Callable[[], None]]] = []
    if command in ("session", "run-day"):
        stages.append(("session", lambda: _session(container, day)))
    if command in ("flatten", "run-day"):
        stages.append(("flatten", lambda: container.flatten.run(day)))
    if command in ("journal", "run-day"):
        stages.append(("journal", lambda: container.journal.run(day)))
    failed = False
    # Each stage runs even if an earlier one failed: a session crash must never skip the flatten.
    for name, stage in stages:
        try:
            stage()
        except Exception as error:
            failed = True
            logger.exception("falha em %s", name)
            container.notifier.send("ORB bot: ERRO", f"{name}: {type(error).__name__}")
    return 1 if failed else 0


def _session(container: Container, day: TradingDay) -> None:
    if reason := halt_reason(container.settings):
        container.notifier.send("ORB bot parado", reason)
        return
    container.session.run(day)


def _status() -> int:
    container = build_container()
    day = _trading_day(container)
    account = container.broker.account()
    positions = container.broker.open_position_symbols()
    logger.info(
        "broker=%s | equity $%.2f (ontem $%.2f) | caixa $%.2f | posições: %s | pregão hoje: %s",
        container.settings.broker, account.equity, account.last_equity,
        account.buying_power, ", ".join(positions) or "nenhuma", "sim" if day else "não",
    )
    return 0


def _trading_day(container: Container) -> TradingDay | None:
    now = container.clock.now()
    day = container.broker.trading_day(now)
    if day is None:
        logger.info("%s: mercado fechado hoje", now.date())
    else:
        logger.info("pregão %s → %s (NY)", f"{day.opens_at:%H:%M}", f"{day.closes_at:%H:%M}")
    return day


def _backtest(args: argparse.Namespace) -> int:
    settings = get_settings()
    symbols = args.symbols.upper().split(",") if args.symbols else settings.symbols
    days = ALPACA_BACKTEST_DAYS if settings.broker == "alpaca" else YAHOO_BACKTEST_DAYS
    start = args.start or args.end - timedelta(days=days)
    path, stats, bench = build_backtest().run(symbols, start, args.end)
    logger.info(
        "%d trades | líquido %+.3fR (±%.3f) | benchmark %+.3fR | edge %+.3fR | max DD %.1fR → %s",
        stats.trades, stats.expectancy_r, stats.std_error_r, bench.expectancy_r,
        stats.expectancy_r - bench.expectancy_r, stats.max_drawdown_r, path,
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orb-bot", description="ORB bot (Alpaca paper)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run-day", help="sessão + flatten + journal (uso diário)")
    sub.add_parser("status", help="saldo, posições e se hoje tem pregão")
    sub.add_parser("session", help="só a janela de entrada")
    sub.add_parser("flatten", help="espera o fechamento − 5min e zera posições")
    sub.add_parser("journal", help="escreve logs/AAAA-MM-DD.md")
    yesterday = date.today() - timedelta(days=1)
    backtest = sub.add_parser("backtest", help="replay histórico da estratégia")
    backtest.add_argument("--start", type=date.fromisoformat,
                          help="padrão: 58 dias (Yahoo) ou 2 anos (Alpaca)")
    backtest.add_argument("--end", type=date.fromisoformat, default=yesterday)
    backtest.add_argument("--symbols", help="ex.: AAPL,MSFT (padrão: WATCHLIST)")
    return parser


if __name__ == "__main__":
    sys.exit(main())
