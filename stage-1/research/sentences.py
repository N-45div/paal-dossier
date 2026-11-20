"""Lines, sentences and prose of served page text (stage-1.md section 4 and Appendix A.1)."""

import re

from .lexicon import LEGAL_SUFFIXES

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_HEADER_LINE = re.compile(r"[A-Z][a-z]+(?:-[A-Z][a-z]+)*:(?=\s|$)")
_TERMINATORS = ".!?"
_CLOSERS = '"”’)'
_MAX_EXCERPT = 500


def _ends_legal_suffix(line: str, index: int) -> bool:
    """True when the '.' at line[index] ends a legal-form suffix written as a whole word."""
    for suffix in LEGAL_SUFFIXES:
        if suffix.endswith("."):
            start = index + 1 - len(suffix)
            matched = start >= 0 and line[start : index + 1] == suffix
        else:
            start = index - len(suffix)
            matched = start >= 0 and line[start:index] == suffix
        if matched and (start == 0 or not line[start - 1].isalnum()):
            return True
    return False


def _split_line(line: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    index = 0
    while index < len(line):
        char = line[index]
        if char not in _TERMINATORS or (char == "." and _ends_legal_suffix(line, index)):
            index += 1
            continue
        end = index + 1
        while end < len(line) and line[end] in _CLOSERS:
            end += 1
        if end == len(line) or line[end].isspace():
            _keep(sentences, line[start:end])
            start = end
        index = end
    _keep(sentences, line[start:])
    return sentences


def _keep(sentences: list[str], piece: str) -> None:
    stripped = piece.strip()
    if stripped:
        sentences.append(stripped)


def split_sentences(text: str) -> list[str]:
    """Split text into lines, then each line into sentences (A.1), without surrounding whitespace."""
    sentences: list[str] = []
    for line in _LINE_BREAK.split(text):
        sentences.extend(_split_line(line))
    return sentences


def page_prose(text: str) -> str:
    """The prose of served page text: everything after the header block, or all of it if there is none."""
    lines = _LINE_BREAK.split(text)
    if not _HEADER_LINE.match(lines[0]):
        return "\n".join(lines)
    for index, line in enumerate(lines):
        if not line.strip():
            return "\n".join(lines[index + 1 :])
    return ""


def collapse_whitespace(text: str) -> str:
    """Every run of whitespace written as one space, with no surrounding whitespace."""
    return " ".join(text.split())


def candidate_excerpts(text: str) -> list[str]:
    """Single-sentence excerpts that a served page text may be cited with (1 to 500 characters)."""
    excerpts = []
    for sentence in split_sentences(page_prose(text)):
        excerpt = collapse_whitespace(sentence)
        if 1 <= len(excerpt) <= _MAX_EXCERPT:
            excerpts.append(excerpt)
    return excerpts
