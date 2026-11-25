import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

from orb_bot.config.constants import (
    BACKTESTS_DIR,
    BENCHMARK_SAMPLES_PER_TRADE,
    BENCHMARK_SEED,
    DEFAULT_MARKET_OPEN,
    ENTRY_WINDOW_END,
    FLATTEN_MINUTES_BEFORE_CLOSE,
    MAX_TRADES_PER_DAY,
    NY_TZ,
    REGULAR_CLOSE,
    SIM_SLIPPAGE_PCT,
)
from orb_bot.domain.ports import MarketDataPort
from orb_bot.domain.simulator import random_entry_benchmark, simulate_bracket, summarize
from orb_bot.domain.strategy import build_opening_range, find_breakout, gap_ok, regular_session
from orb_bot.domain.types import BacktestStats, Bar, TradeResult
from orb_bot.infra.markdown_writer import MarkdownWriter

_LOOKBACK_FOR_FIRST_CLOSE = timedelta(days=10)


class BacktestService:
    def __init__(self, data: MarketDataPort, writer: MarkdownWriter) -> None:
        self._data = data
        self._writer = writer

    def run(
        self, symbols: list[str], start: date, end: date
    ) -> tuple[Path, BacktestStats, BacktestStats]:
        bars = self._data.intraday_bars(
            symbols,
            datetime.combine(start, time.min, NY_TZ),
            datetime.combine(end, REGULAR_CLOSE, NY_TZ),
        )
        closes = self._data.daily_closes(symbols, start - _LOOKBACK_FOR_FIRST_CLOSE, end)
        rng = random.Random(BENCHMARK_SEED)
        results: list[TradeResult] = []
        benchmark: list[TradeResult] = []
        for symbol in symbols:
            trades, twins = self._replay_symbol(
                symbol, bars.get(symbol, []), closes.get(symbol, {}), rng
            )
            results += trades
            benchmark += twins
        results.sort(key=lambda r: r.day)
        stats, bench_stats = summarize(results), summarize(benchmark)
        path = BACKTESTS_DIR / f"orb-{start}-{end}.md"
        self._writer.write(path, _render(symbols, start, end, results, stats, bench_stats))
        return path, stats, bench_stats

    def _replay_symbol(
        self, symbol: str, bars: list[Bar], closes: dict[date, float], rng: random.Random
    ) -> tuple[list[TradeResult], list[TradeResult]]:
        by_day: dict[date, list[Bar]] = defaultdict(list)
        for bar in bars:
            by_day[bar.start.date()].append(bar)
        results: list[TradeResult] = []
        benchmark: list[TradeResult] = []
        for day, day_bars in sorted(by_day.items()):
            prior = [d for d in closes if d < day]
            if not prior:
                continue
            opens_at = datetime.combine(day, DEFAULT_MARKET_OPEN, NY_TZ)
            closes_at = datetime.combine(day, REGULAR_CLOSE, NY_TZ)
            session = regular_session(day_bars, opens_at, closes_at)
            opening_range = build_opening_range(session, opens_at)
            if opening_range is None or not gap_ok(opening_range, closes[max(prior)]):
                continue
            signal = find_breakout(symbol, session, opening_range, closes_at)
            if signal is None:
                continue
            # Early-close days simply run out of bars; the last bar becomes the exit.
            flatten_at = closes_at - timedelta(minutes=FLATTEN_MINUTES_BEFORE_CLOSE)
            results.append(simulate_bracket(signal, session, flatten_at))
            window_end = datetime.combine(day, ENTRY_WINDOW_END, NY_TZ)
            window = [b for b in session if opening_range.ends_at <= b.start and b.end <= window_end]
            benchmark += random_entry_benchmark(
                signal, window, session, flatten_at, rng, BENCHMARK_SAMPLES_PER_TRADE
            )
        return results, benchmark


def _render(
    symbols: list[str],
    start: date,
    end: date,
    results: list[TradeResult],
    stats: BacktestStats,
    bench: BacktestStats,
) -> str:
    edge = stats.expectancy_r - bench.expectancy_r
    lines = [
        f"# Backtest ORB — {start} a {end}",
        "",
        f"Símbolos: {', '.join(symbols)}",
        "",
        "## Geral (líquido de slippage)",
        _stats_table([("ESTRATÉGIA", stats), ("BENCHMARK aleatório", bench)]),
        "",
        f"**Edge sobre entrada aleatória:** {edge:+.3f}R por trade "
        f"(erro padrão da estratégia ±{stats.std_error_r:.3f}R).",
        "",
        "## Por símbolo",
        _stats_table([(s, summarize([r for r in results if r.symbol == s])) for s in symbols]),
        "",
        "## Leitura",
        f"- Custo: slippage de {SIM_SLIPPAGE_PCT:.2%} em entrada, stop e flatten "
        "(alvo é ordem limite, sem slippage).",
        "- Benchmark: mesmo dia, mesmo risco por ação e mesmo alvo, comprando num candle "
        f"aleatório da janela de entrada ({BENCHMARK_SAMPLES_PER_TRADE} sorteios por trade).",
        "- Edge real exige expectância líquida > 0 **e** acima do benchmark por mais de "
        "2 erros padrão.",
        "- Stop e alvo no mesmo candle contam como stop (pessimista).",
        "- Cada símbolo é independente; o bot ao vivo faz no máximo "
        f"{MAX_TRADES_PER_DAY} trades/dia no total.",
    ]
    return "\n".join(lines) + "\n"


def _stats_table(rows: list[tuple[str, BacktestStats]]) -> str:
    header = "| | trades | win rate | bruto | custo | **líquido** | ± erro | max DD |\n"
    header += "|---|---|---|---|---|---|---|---|\n"
    body = "\n".join(
        f"| {name} | {s.trades} | {s.win_rate:.0%} | {s.gross_expectancy_r:+.3f}R | "
        f"{s.gross_expectancy_r - s.expectancy_r:.3f}R | **{s.expectancy_r:+.3f}R** | "
        f"{s.std_error_r:.3f} | {s.max_drawdown_r:.1f}R |"
        for name, s in rows
    )
    return header + body
