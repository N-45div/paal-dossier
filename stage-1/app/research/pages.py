"""Served page text: header lines and prose (spec section 4, Pages)."""
from __future__ import annotations

import re

_HEADER_LINE = re.compile(r"^[A-Z][a-z]+(?:-[A-Z][a-z]+)*:(?:\s|$)")
_LINE_BREAK = re.compile(r"\r\n|\n|\r")


def split_lines(text: str) -> list[str]:
    return _LINE_BREAK.split(text)


def split_page(text: str) -> tuple[list[str], str]:
    """Split served text into (header lines, prose).

    The header exists only when the first line is a header line; it ends at
    the first empty line. A text with no header is all prose.
    """
    lines = split_lines(text)
    if not _HEADER_LINE.match(lines[0]):
        return [], text
    for i, line in enumerate(lines):
        if line == "":
            return lines[:i], "\n".join(lines[i + 1:])
    return lines, ""


def prose_of(text: str) -> str:
    return split_page(text)[1]
