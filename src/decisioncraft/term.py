"""Terminal output for people: plain progress lines, colour only when it helps.

Colour is used only when the stream is a terminal, NO_COLOR is unset and TERM is not
"dumb". There are no spinners or redrawn lines, so output reads the same in a log file.
Progress and notes go to stderr; results go to stdout.
"""

from __future__ import annotations

import os
import sys

_CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "blue": "34"}


class Term:
    def __init__(self, *, quiet: bool = False, no_color: bool = False):
        self.quiet = quiet
        self.no_color = no_color

    def color_on(self, stream) -> bool:
        if self.no_color or os.environ.get("NO_COLOR") is not None:
            return False
        if os.environ.get("TERM") == "dumb":
            return False
        return bool(getattr(stream, "isatty", lambda: False)())

    def paint(self, text: str, style: str, stream=None) -> str:
        stream = stream or sys.stderr
        if not self.color_on(stream):
            return text
        return f"\033[{_CODES[style]}m{text}\033[0m"

    def say(self, text: str = "") -> None:
        """A progress or note line on stderr. Silent with --quiet."""
        if not self.quiet:
            print(text, file=sys.stderr, flush=True)

    def warn(self, text: str) -> None:
        print(self.paint("Note: ", "yellow") + text, file=sys.stderr, flush=True)

    def mark(self, status: str, stream=None) -> str:
        """A status word for check lists: works without colour or symbols."""
        stream = stream or sys.stdout
        word = {"ok": "ok  ", "warn": "note", "fail": "fix "}[status]
        style = {"ok": "green", "warn": "yellow", "fail": "red"}[status]
        return self.paint(word, style, stream)


def interactive() -> bool:
    """True when a person can answer prompts: stdin and stderr are both terminals."""
    return sys.stdin is not None and sys.stdin.isatty() and sys.stderr.isatty()
