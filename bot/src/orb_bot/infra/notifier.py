import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled and sys.platform == "darwin"

    def send(self, title: str, message: str) -> None:
        logger.info("%s — %s", title, message)
        if not self._enabled:
            return
        script = f"display notification {_quote(message)} with title {_quote(title)}"
        try:
            subprocess.run(["osascript", "-e", script], check=False, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            logger.warning("notification failed", exc_info=True)


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
