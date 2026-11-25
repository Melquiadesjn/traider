from datetime import timedelta

from conftest import SESSION_OPEN

from orb_bot.infra.markdown_writer import MarkdownWriter
from orb_bot.services.clock import next_bar_check


def test_bot_section_preserves_manual_notes(tmp_path):
    path = tmp_path / "2026-10-21.md"
    writer = MarkdownWriter()
    writer.write_bot_section(path, "primeira", "# Journal\n")
    path.write_text(path.read_text() + "\nminha nota\n")
    writer.write_bot_section(path, "segunda", "# Journal\n")
    text = path.read_text()
    assert "segunda" in text and "primeira" not in text and "minha nota" in text


def test_next_bar_check_waits_for_bar_close():
    now = SESSION_OPEN + timedelta(minutes=16)
    assert next_bar_check(now, SESSION_OPEN) == SESSION_OPEN + timedelta(minutes=20, seconds=10)
