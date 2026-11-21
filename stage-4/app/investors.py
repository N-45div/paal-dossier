"""The `investors` field (stage 4, R4B): investor names from excerpts, members and the decision.

Pure: no IO. An investor name is taken from an excerpt by Appendix A for `investors`
(``investor_names``). A name is a member when the field's candidates support it strongly
enough (``is_member``); the value is the sorted list of member names, and the field's
candidates, citations and times follow from the members. Origins and corroboration are
left to ``app.origins`` (R4A).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.candidates import Candidate, normalise_value
from app.domain import normalise_domain
from urllib.parse import urlsplit
from app.selection import rank
from app.support import _AMOUNT_RE, _LETTER_RUN, _gate, _is_capitalised, _word_at, _word_re

INVESTOR_PHRASES: tuple[str, ...] = ("investor", "investors", "led by", "backed by", "participated")
INVESTOR_SUFFIXES: tuple[str, ...] = (
    "Ventures", "Capital", "Partners", "Fund", "Investments", "Holdings", "Equity",
)
_LEAD_RE = re.compile(r"(?<![^\W_])(?:led by|backed by) (?=[^\W\d_])", re.IGNORECASE)


def _runs(masked: str) -> list[list[str]]:
    """Runs of capitalised words joined by single spaces, each not part of a longer run (A.4)."""
    runs: list[list[str]] = []
    run: list[str] = []
    previous_end = -2
    for match in _LETTER_RUN.finditer(masked):
        word = match.group()
        valid = _word_at(masked, match.start()) == word and _is_capitalised(word)
        joined = bool(run) and match.start() == previous_end + 1 and masked[previous_end] == " "
        if valid and joined:
            run.append(word)
        else:
            if run:
                runs.append(run)
            run = [word] if valid else []
        previous_end = match.end()
    if run:
        runs.append(run)
    return runs


def _run_after_lead(text: str) -> set[str]:
    """The capitalised run that starts directly after `led by` / `backed by` and one space."""
    names: set[str] = set()
    for match in _LEAD_RE.finditer(text):
        words: list[str] = []
        position = match.end()
        while True:
            word = _word_at(text, position)
            if word is None or not _is_capitalised(word):
                break
            words.append(word)
            position += len(word)
            if not text.startswith(" ", position):
                break
            position += 1
        if words:
            names.add(" ".join(words))
    return names


def investor_names(domain: str, excerpt: str) -> set[str]:
    """Investor names the excerpt supports under Appendix A for `investors` (stage 4)."""
    gated = _gate(domain, excerpt)
    if gated is None:
        return set()
    text, domain, name = gated
    if _word_re(INVESTOR_PHRASES).search(text) is None:
        return set()
    masked = _word_re((domain, name)).sub("|", text)
    masked = _word_re(INVESTOR_PHRASES).sub("|", masked)
    names = {" ".join(run) for run in _runs(masked)
             if len(run) >= 2 and run[-1] in INVESTOR_SUFFIXES}
    if _AMOUNT_RE.search(text):
        names |= _run_after_lead(text)
    return names


def is_member(candidates_with_name: list[Candidate], origins: set[str]) -> bool:
    """A name is a member when a candidate with it is `own` or `filing`, or its candidates have
    two or more distinct origins (stage 4, `investors`). ``origins`` is the set of their origins."""
    if any(c.kind in ("own", "filing") for c in candidates_with_name):
        return True
    return len(origins) >= 2


def url_host(candidate: Candidate) -> str:
    """Stand-in origin of a candidate: the normalised host of its URL. R4A's origin (the page's
    First-Published-By, canonical chain, lookalike or registrant) replaces this when it lands."""
    return normalise_domain(urlsplit(candidate.url).hostname or "") or ""


def candidate_origin(candidate: Candidate) -> str:
    """A candidate's origin (R4A): its stored origin, or the host of its URL when it has none."""
    return candidate.origin if candidate.origin is not None else url_host(candidate)


@dataclass(frozen=True)
class InvestorsDecision:
    """The field's status, its members (sorted names) and its candidates in rank order."""

    status: str  # "known" | "unknown"
    members: tuple[str, ...]
    ranked: tuple[Candidate, ...]

    @property
    def value(self) -> list[str] | None:
        return list(self.members) if self.members else None

    def _with(self, name: str) -> list[Candidate]:
        return [c for c in self.ranked if normalise_value(c.value) == name]

    @property
    def selected(self) -> tuple[Candidate, ...]:
        return tuple(c for c in self.ranked if normalise_value(c.value) in self.members)

    def member_true_from(self, name: str) -> date | None:
        dates = [c.true_from for c in self._with(name) if c.true_from is not None]
        return min(dates) if dates else None

    @property
    def true_from(self) -> date | None:
        """The latest of the members' true_from, or None when the value is null or any is null."""
        if not self.members:
            return None
        dates = [self.member_true_from(name) for name in self.members]
        return None if any(d is None for d in dates) else max(dates)

    @property
    def citations(self) -> list[dict[str, str]]:
        cited: list[dict[str, str]] = []
        for name in self.members:
            for candidate in self._with(name):
                cited.append({"url": candidate.url, "excerpt": candidate.excerpt,
                              "provider": candidate.provider})
        return cited


def decide_investors(candidates: list[Candidate], origin_of) -> InvestorsDecision:
    """The `investors` decision from the field's candidates. ``origin_of(candidate)`` gives a
    candidate's origin (R4A); the members are the names that pass ``is_member``."""
    ranked = tuple(rank(candidates))
    names = {normalise_value(c.value) for c in ranked}
    members = []
    for name in sorted(names):
        with_name = [c for c in ranked if normalise_value(c.value) == name]
        origins = {origin_of(c) for c in with_name}
        if is_member(with_name, origins):
            members.append(name)
    status = "known" if members else "unknown"
    return InvestorsDecision(status=status, members=tuple(members), ranked=ranked)
