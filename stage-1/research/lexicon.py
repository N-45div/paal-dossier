"""Phrase and suffix tables from stage-1.md Appendix A.3 and A.4."""

STATEMENT_PHRASES = {
    "legal_name": (
        "legal name",
        "registered name",
        "registered as",
        "registered company",
        "legal entity",
        "name of record",
    ),
    "hq_city": (
        "headquartered in",
        "headquarters in",
        "head office in",
        "based in",
        "registered office in",
        "registered seat in",
    ),
    "ceo": ("chief executive officer", "chief executive", "CEO"),
    "founded_year": ("founded", "founding", "established", "incorporated"),
    "headcount_range": ("employs", "employees", "staff", "people", "headcount", "workforce"),
    "funding_total": ("raised", "funding", "invested", "investment"),
}

NEGATING_PHRASES = (
    "in talks to",
    "plans to",
    "planning to",
    "wants to",
    "expects to",
    "hopes to",
    "aims to",
    "seeking",
    "could",
    "would",
    "might",
    "reportedly",
    "rumoured",
    "former",
    "formerly",
    "will become",
    "not",
)

# Matched exactly as written (case-sensitive), each with no letter or digit after it.
LEGAL_SUFFIXES = (
    "Inc.",
    "Corp.",
    "LLC",
    "LLP",
    "L.P.",
    "Ltd",
    "Limited",
    "Pty Ltd",
    "plc",
    "PLC",
    "GmbH",
    "AG",
    "KG",
    "SE",
    "AS",
    "A/S",
    "ASA",
    "AB",
    "Oy",
    "Oyj",
    "B.V.",
    "N.V.",
    "S.A.",
    "S.A.S.",
    "S.L.",
    "S.r.l.",
    "S.p.A.",
    "s.r.o.",
    "a.s.",
    "K.K.",
)

SCALE_WORDS = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
SCALE_SUFFIXES = {"k": 1_000, "m": 1_000_000, "mn": 1_000_000, "bn": 1_000_000_000}
