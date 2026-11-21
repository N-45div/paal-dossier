"""The `executives` field (stage 3): one selected person per title, cfo, coo, cto (§4 stage 3).

Pure: no IO. Each title's candidates are ranked by the stage-2 selection rule
(``app.selection.rank``), and the highest-ranked one is that title's person. Members are
listed in the order of ``TITLES``; citations are, for each member, the candidates with its
title and name, in rank order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.candidates import Candidate, normalise_value
from app.selection import rank
from app.support import TITLES


@dataclass(frozen=True)
class ExecutivesDecision:
    """The field's status, its members (``{"title", "name"}``), and the candidates by title."""

    status: str  # "known" | "contested" | "unknown"
    selected: tuple[Candidate, ...]  # the top candidate of each title that has one
    ranked: tuple[Candidate, ...]  # every candidate: by title order, rank order within a title

    @property
    def value(self) -> list[dict[str, str]] | None:
        if not self.selected:
            return None
        return [{"title": c.title, "name": normalise_value(c.value)} for c in self.selected]

    @property
    def true_from(self) -> date | None:
        """The latest of the members' ``true_from``, or None when any member's is None."""
        if not self.selected:
            return None
        dates = [c.true_from for c in self.selected]
        return None if any(d is None for d in dates) else max(dates)

    @property
    def citations(self) -> list[dict[str, str]]:
        cited: list[dict[str, str]] = []
        for member in self.selected:
            name = normalise_value(member.value)
            for candidate in self.ranked:
                if candidate.title == member.title and normalise_value(candidate.value) == name:
                    cited.append({"url": candidate.url, "excerpt": candidate.excerpt,
                                  "provider": candidate.provider})
        return cited


def decide_executives(candidates: list[Candidate]) -> ExecutivesDecision:
    selected: list[Candidate] = []
    ranked: list[Candidate] = []
    names_by_title: dict[str, set[Any]] = {}
    for title in TITLES:
        of_title = rank([c for c in candidates if c.title == title])
        if not of_title:
            continue
        selected.append(of_title[0])
        ranked.extend(of_title)
        names_by_title[title] = {normalise_value(c.value) for c in of_title}
    if not selected:
        status = "unknown"
    elif any(len(names) > 1 for names in names_by_title.values()):
        status = "contested"
    else:
        status = "known"
    return ExecutivesDecision(status=status, selected=tuple(selected), ranked=tuple(ranked))
