"""The Nimble provider, reached only through web_router (stage-1.md section 2)."""

from dataclasses import dataclass

from web_router.exceptions import ProviderError

from .calls import Refused, Unanswered
from .fields import FIELDS

PROVIDER = "nimble"
MAX_RESULTS = 10
SEARCH_TIMEOUT_S = 60.0
EXTRACT_TIMEOUT_S = 60.0
RESEARCH_TIMEOUT_S = 120.0

RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "legal_name": {"type": "string"},
        "hq_city": {"type": "string"},
        "ceo": {"type": "string"},
        "founded_year": {"type": "integer"},
        "headcount_range": {"type": "string"},
        "funding_total": {"type": "integer"},
    },
}


@dataclass(frozen=True)
class Citation:
    field: str
    url: str
    excerpt: str


def _translate(exc: BaseException) -> Exception:
    """A provider error with a status is a refusal; a call with no status (timeout, connection) is unanswered."""
    if isinstance(exc, ProviderError) and exc.status_code is not None and exc.kind != "target":
        return Refused(str(exc), rate_limited=exc.kind == "rate_limit")
    return Unanswered(str(exc))


class NimbleProvider:
    def __init__(self, router) -> None:
        self._router = router

    def _call(self, call):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001
            raise _translate(exc) from exc

    def search(self, query: str) -> list[str]:
        """URLs of the results of one lite search, in rank order."""
        response = self._call(
            lambda: self._router.search(
                query,
                provider=PROVIDER,
                max_results=MAX_RESULTS,
                search_depth="lite",
                timeout=SEARCH_TIMEOUT_S,
            )
        )
        return [result.url for result in response.results]

    def extract(self, url: str) -> str | None:
        """The served text of the page at url, or None when the provider has no page for it."""
        try:
            response = self._router.extract([url], provider=PROVIDER, timeout=EXTRACT_TIMEOUT_S)
        except ProviderError as exc:
            if exc.kind == "target":
                return None
            raise _translate(exc) from exc
        except Exception as exc:  # noqa: BLE001
            raise _translate(exc) from exc
        if not response.documents:
            return None
        return response.documents[0].content

    def research(self, query: str) -> list[Citation]:
        """Citations of one research run asking for the six fields."""
        response = self._call(
            lambda: self._router.research(
                query,
                provider=PROVIDER,
                output_schema=RESEARCH_SCHEMA,
                timeout=RESEARCH_TIMEOUT_S,
            )
        )
        citations = []
        for citation in response.citations:
            field = (citation.field or "").removeprefix("$.")
            if field in FIELDS:
                citations.append(Citation(field, citation.url, citation.snippet))
        return citations
