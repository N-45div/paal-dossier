"""Route table: method and path templates mapped to handlers."""

import re
from dataclasses import dataclass
from typing import Callable

from .errors import method_not_allowed, not_found

_PARAM = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class Route:
    method: str
    template: str
    pattern: re.Pattern
    handler: Callable
    public: bool


class Router:
    def __init__(self) -> None:
        self._routes: list[Route] = []

    def add(self, method: str, template: str, handler: Callable, *, public: bool = False) -> None:
        regex = _PARAM.sub(lambda m: f"(?P<{m.group(1)}>[^/]+)", re.escape(template).replace(r"\{", "{").replace(r"\}", "}"))
        self._routes.append(Route(method, template, re.compile(f"^{regex}$"), handler, public))

    def match(self, method: str, path: str) -> tuple[Route, dict[str, str]]:
        path_matched = False
        for route in self._routes:
            found = route.pattern.match(path)
            if found is None:
                continue
            path_matched = True
            if route.method == method:
                return route, found.groupdict()
        if path_matched:
            raise method_not_allowed()
        raise not_found()
