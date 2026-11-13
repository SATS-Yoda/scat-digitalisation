import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import Request

from .queries import plant_for

SESSION_COOKIE = "session"
CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class Forbidden(Exception):
    pass


class Unauthenticated(Exception):
    pass


@dataclass(frozen=True)
class User:
    id: str
    plants: frozenset[str]
    is_admin: bool = False


@dataclass(frozen=True)
class Identity:
    """Who the identity provider says signed in: a stable id and the group ids it carries."""

    id: str
    groups: frozenset[str]


class IdentityError(Exception):
    """The provider rejected the sign-in (bad state, expired code, denied consent)."""


class IdentityProvider(Protocol):
    """Shaped like MSAL's confidential-client authorization-code flow, so the real adapter
    is a thin wrapper and tests use a fake."""

    def begin(self) -> tuple[str, dict]:
        """Return the URL to send the browser to and the flow state to keep until the
        callback. The state must contain a `state` key."""

    def complete(self, flow: dict, params: dict) -> Identity:
        """Finish the flow from the callback's query parameters. Raise IdentityError."""


class SessionStore(Protocol):
    def get(self, key: str) -> dict | None: ...

    def pop(self, key: str) -> dict | None: ...

    def put(self, key: str, value: dict, ttl_s: int) -> None: ...

    def delete(self, key: str) -> None: ...


class InMemorySessionStore:
    # ceiling: per-process, so sessions do not survive a restart and are not shared between
    # pods; the Redis-backed store replaces it before deployment (build order step 5).
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._items: dict[str, tuple[float, dict]] = {}

    def get(self, key: str) -> dict | None:
        item = self._items.get(key)
        if item is None:
            return None
        if item[0] <= self._clock():
            del self._items[key]
            return None
        return item[1]

    def pop(self, key: str) -> dict | None:
        value = self.get(key)
        self._items.pop(key, None)
        return value

    def put(self, key: str, value: dict, ttl_s: int) -> None:
        self._items[key] = (self._clock() + ttl_s, value)

    def delete(self, key: str) -> None:
        self._items.pop(key, None)


@dataclass(frozen=True)
class GroupMap:
    """Entra group object ids that grant each plant and admin rights."""

    icc1: str
    icc2: str
    admin: str


@dataclass(frozen=True)
class AuthConfig:
    provider: IdentityProvider
    store: SessionStore
    groups: GroupMap
    session_ttl_s: int = 8 * 3600
    # Off only for plain-http local development.
    secure_cookie: bool = True


DEV_USER = User(id="dev-user", plants=frozenset({"ICC1", "ICC2"}), is_admin=True)


def user_from_identity(identity: Identity, groups: GroupMap) -> User:
    plants = frozenset(
        plant
        for plant, group in (("ICC1", groups.icc1), ("ICC2", groups.icc2))
        if group in identity.groups
    )
    return User(identity.id, plants, groups.admin in identity.groups)


def start_session(auth: AuthConfig, user: User) -> tuple[str, str]:
    """Store the user server-side and return (session id, csrf token)."""
    session_id, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    data = {"id": user.id, "plants": sorted(user.plants), "is_admin": user.is_admin, "csrf": csrf}
    # Group membership is read at sign-in, so a change takes effect at the next sign-in or
    # when the session expires.
    auth.store.put(f"session:{session_id}", data, auth.session_ttl_s)
    return session_id, csrf


def current_user(request: Request) -> User:
    """The signed-in user. With no auth configured (local development and tests only; the
    process refuses to start that way outside development) it is a fixed admin."""
    auth: AuthConfig | None = request.app.state.auth
    if auth is None:
        return DEV_USER
    session_id = request.cookies.get(SESSION_COOKIE)
    data: dict[str, Any] | None = auth.store.get(f"session:{session_id}") if session_id else None
    if data is None:
        raise Unauthenticated("Sign in required")
    if request.method not in _SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not hmac.compare_digest(sent.encode(), data["csrf"].encode()):
            raise Forbidden("Missing or wrong CSRF token")
    return User(data["id"], frozenset(data["plants"]), data["is_admin"])


def require_plant(user: User, airline: str) -> None:
    plant = plant_for(airline)
    if plant not in user.plants:
        raise Forbidden(f"{airline} flights belong to {plant}, which this user cannot act on")


def require_admin(user: User) -> None:
    if not user.is_admin:
        raise Forbidden("Only an administrator can change console settings")
