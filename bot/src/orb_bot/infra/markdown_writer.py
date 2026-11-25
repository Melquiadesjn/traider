from pathlib import Path

BOT_SECTION_START = "<!-- bot:start -->"
BOT_SECTION_END = "<!-- bot:end -->"


class MarkdownWriter:
    def write_bot_section(self, path: Path, section: str, skeleton: str) -> None:
        """Replaces only the bot-owned block so hand-written notes survive reruns."""
        block = f"{BOT_SECTION_START}\n{section.strip()}\n{BOT_SECTION_END}"
        text = path.read_text() if path.exists() else skeleton
        if BOT_SECTION_START in text and BOT_SECTION_END in text:
            head, rest = text.split(BOT_SECTION_START, 1)
            _, tail = rest.split(BOT_SECTION_END, 1)
            text = head + block + tail
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
        self.write(path, text)

    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
