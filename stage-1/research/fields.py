"""The six dossier fields (stage-1.md section 4) and the headcount bands."""

FIELDS = (
    "legal_name",
    "hq_city",
    "ceo",
    "founded_year",
    "headcount_range",
    "funding_total",
)

# (lowest, highest, label); the last band is open-ended.
HEADCOUNT_RANGES = (
    (1, 10, "1-10"),
    (11, 50, "11-50"),
    (51, 200, "51-200"),
    (201, 500, "201-500"),
    (501, 1000, "501-1000"),
    (1001, 5000, "1001-5000"),
    (5001, 10000, "5001-10000"),
    (10001, None, "10001+"),
)


def headcount_range_for(count: int) -> str | None:
    """Return the §4 range that contains a headcount of 1 or more, else None."""
    if count < 1:
        return None
    for low, high, label in HEADCOUNT_RANGES:
        if high is None or count <= high:
            return label
    return None  # unreachable: the last band is open-ended
