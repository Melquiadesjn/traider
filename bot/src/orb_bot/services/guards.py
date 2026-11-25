from orb_bot.config.constants import KILL_SWITCH_FILE
from orb_bot.config.settings import Settings


def halt_reason(settings: Settings) -> str | None:
    if not settings.bot_enabled:
        return "BOT_ENABLED=false"
    if KILL_SWITCH_FILE.exists():
        return f"kill switch ativo ({KILL_SWITCH_FILE.name})"
    return None
