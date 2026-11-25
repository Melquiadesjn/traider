from conftest import SESSION_OPEN

from orb_bot.config.constants import MAX_TRADES_PER_DAY
from orb_bot.domain.risk import check_limits, size_position
from orb_bot.domain.types import AccountSnapshot, Signal

ACCOUNT = AccountSnapshot(equity=10_000, last_equity=10_000, buying_power=20_000)


def _signal(entry: float, stop: float) -> Signal:
    return Signal("AAPL", SESSION_OPEN, entry=entry, stop=stop, target=entry + 2 * (entry - stop))


def test_size_by_risk():
    # $200 risk / $1 per share = 200 shares, but 25% cap = $2,500 / $10 = 250
    assert size_position(_signal(10.0, 9.0), ACCOUNT) == 200


def test_size_capped_by_notional():
    # risk allows 400 shares of a $100 stock; 25% of equity allows 25
    assert size_position(_signal(100.0, 99.5), ACCOUNT) == 25


def test_tiny_range_is_skipped():
    assert size_position(_signal(100.0, 99.99), ACCOUNT) == 0


def test_limits_block_only_at_the_daily_trade_cap():
    assert check_limits(ACCOUNT, 10_000, trades_today=MAX_TRADES_PER_DAY - 1).allowed
    assert not check_limits(ACCOUNT, 10_000, trades_today=MAX_TRADES_PER_DAY).allowed


def test_limits_block_daily_loss():
    down = AccountSnapshot(equity=9_400, last_equity=10_000, buying_power=9_400)
    assert not check_limits(down, 9_400, trades_today=0).allowed


def test_limits_block_weekly_loss():
    assert not check_limits(ACCOUNT, week_start_equity=11_200, trades_today=0).allowed


def test_limits_allow_fresh_day():
    assert check_limits(ACCOUNT, 10_000, trades_today=0).allowed
