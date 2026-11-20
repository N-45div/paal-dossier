"""Provider errors: refusal with a status is free, a missing page or a timeout is charged (stage-1.md section 9)."""

from web_router.exceptions import ProviderError

from research.calls import Refused, Unanswered
from research.nimble import NimbleProvider, _translate


def provider_error(kind, status_code):
    error = ProviderError("nimble", "injected")
    error.kind = kind
    error.status_code = status_code
    return error


class _Router:
    def __init__(self, raises=None, documents=None):
        self._raises = raises
        self._documents = documents or []

    def extract(self, urls, **_):
        if self._raises:
            raise self._raises
        return type("Response", (), {"documents": self._documents})()


def test_status_error_is_refused():
    error = provider_error("upstream", 500)
    assert isinstance(_translate(error), Refused)


def test_rate_limit_is_refused_and_marked():
    error = provider_error("rate_limit", 429)
    translated = _translate(error)
    assert isinstance(translated, Refused) and translated.rate_limited


def test_status_without_kind_target_is_refused_but_target_is_an_answer():
    target = provider_error("target", 404)
    assert isinstance(_translate(target), Unanswered)


def test_connection_failure_without_status_is_unanswered():
    error = provider_error("upstream", None)
    assert isinstance(_translate(error), Unanswered)


def test_missing_page_extract_returns_none_and_is_answered():
    router = _Router(raises=provider_error("target", 404))
    assert NimbleProvider(router).extract("https://gone.test/x") is None


def test_extract_returns_served_text():
    document = type("Document", (), {"content": "Kind: own\n\nBody."})()
    assert NimbleProvider(_Router(documents=[document])).extract("https://a.test/x") == "Kind: own\n\nBody."
