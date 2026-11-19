import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.domain import InvalidDomain, normalise_domain  # noqa: E402


@pytest.mark.parametrize("raw", ["Acme-Robotics.TEST.", "www.acme-robotics.test", " acme-robotics.test "])
def test_same_company(raw):
    assert normalise_domain(raw) == "acme-robotics.test"


@pytest.mark.parametrize(
    "raw", ["", "acme", "https://a.test", "a.test/x", "-a.test", "a-.test", "a..test", "a_b.test", "www.a", "a.test..", "x" * 64 + ".test", ("a." * 130) + "te"]
)
def test_invalid(raw):
    with pytest.raises(InvalidDomain):
        normalise_domain(raw)


def test_only_one_www_and_dot_removed():
    assert normalise_domain("www.www.a.test") == "www.a.test"
