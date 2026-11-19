"""Signup and login (§6). Both are public; every other endpoint needs a bearer token."""

from .wire import parse_json, require_object, required_string


def register(router) -> None:
    router.add("POST", "/auth/signup", signup, public=True)
    router.add("POST", "/auth/login", login, public=True)


def signup(app, request):
    body = require_object(parse_json(request.body))
    email = required_string(body, "email")
    password = required_string(body, "password")
    display_name = required_string(body, "display_name")
    account = app.store.signup(email, password, display_name)
    return 201, {"user_id": account.user_id, "display_name": account.display_name, "token": account.token}


def login(app, request):
    body = require_object(parse_json(request.body))
    email = required_string(body, "email")
    password = required_string(body, "password")
    account = app.store.login(email, password)
    return 200, {"user_id": account.user_id, "display_name": account.display_name, "token": account.token}
