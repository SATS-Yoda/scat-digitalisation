"""The real identity provider (Entra via MSAL) and session store (Redis)."""

import json

import msal
import redis

from .auth import Identity, IdentityError


class EntraProvider:
    """Authorization-code flow with PKCE as a confidential client. The app registration
    must emit the `groups` claim (group object ids)."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, redirect_uri: str):
        self._redirect_uri = redirect_uri
        self._app = msal.ConfidentialClientApplication(
            client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
        )

    def begin(self) -> tuple[str, dict]:
        # No resource scopes: the console only needs to know who signed in.
        flow = self._app.initiate_auth_code_flow(scopes=[], redirect_uri=self._redirect_uri)
        if "auth_uri" not in flow:
            raise IdentityError(flow.get("error_description") or "Entra refused to start sign-in")
        return flow["auth_uri"], flow

    def complete(self, flow: dict, params: dict) -> Identity:
        try:
            result = self._app.acquire_token_by_auth_code_flow(flow, params)
        except ValueError as exc:  # state mismatch
            raise IdentityError(str(exc)) from exc
        if "error" in result:
            raise IdentityError(result.get("error_description") or result["error"])
        claims = result["id_token_claims"]
        if "_claim_names" in claims:
            # More than 200 groups: Entra sends a pointer instead of the list.
            raise IdentityError(
                "Too many groups for the token; restrict the app to assigned groups"
            )
        return Identity(claims["oid"], frozenset(claims.get("groups", [])))


class RedisSessionStore:
    def __init__(self, client: redis.Redis, prefix: str = "scat-console:"):
        self._r = client
        self._prefix = prefix

    @classmethod
    def from_url(cls, url: str) -> "RedisSessionStore":
        return cls(redis.Redis.from_url(url, decode_responses=True))

    def _load(self, raw: str | None) -> dict | None:
        return json.loads(raw) if raw is not None else None

    def get(self, key: str) -> dict | None:
        return self._load(self._r.get(self._prefix + key))

    def pop(self, key: str) -> dict | None:
        return self._load(self._r.getdel(self._prefix + key))

    def put(self, key: str, value: dict, ttl_s: int) -> None:
        self._r.set(self._prefix + key, json.dumps(value), ex=ttl_s)

    def delete(self, key: str) -> None:
        self._r.delete(self._prefix + key)
