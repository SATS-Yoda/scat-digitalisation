"""Sign-in, sessions, CSRF and plant scoping, against a fake identity provider."""

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.auth import (
    AuthConfig,
    GroupMap,
    Identity,
    IdentityError,
    InMemorySessionStore,
)

GROUPS = GroupMap(icc1="g-icc1", icc2="g-icc2", admin="g-admin")
SQ856_P06H = "/api/flights/SQ/856/2026-11-13/stages/P06H"
QR943_P24H = "/api/flights/QR/943/2026-11-13/stages/P24H"


class FakeProvider:
    """Hands out one identity per `code` query value; anything else is refused."""

    def __init__(self):
        self.identities: dict[str, Identity] = {}
        self.n = 0

    def begin(self):
        self.n += 1
        return f"https://idp.test/authorize?state=s{self.n}", {"state": f"s{self.n}"}

    def complete(self, flow, params):
        identity = self.identities.get(params.get("code", ""))
        if identity is None:
            raise IdentityError("unknown code")
        return identity


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def store():
    return InMemorySessionStore()


@pytest.fixture
def signed_out(engine, sender, provider, store):
    app = create_app(engine, sender, AuthConfig(provider, store, GROUPS, secure_cookie=False))
    return TestClient(app, follow_redirects=False)


def sign_in(client, provider, groups, code="c1"):
    provider.identities[code] = Identity("oid-1", frozenset(groups))
    state = client.get("/auth/login").headers["location"].split("state=")[1]
    return client.get("/auth/callback", params={"code": code, "state": state})


def test_api_needs_a_session(signed_out):
    assert signed_out.get("/api/flights").status_code == 401
    assert signed_out.get("/api/me").status_code == 401
    assert signed_out.get("/health").status_code == 200


def test_sign_in_sets_an_httponly_session_and_reads_work(signed_out, provider):
    response = sign_in(signed_out, provider, ["g-icc2"])
    assert response.status_code == 307
    assert "httponly" in response.headers["set-cookie"].lower()
    me = signed_out.get("/api/me").json()
    assert (me["id"], me["plants"], me["is_admin"]) == ("oid-1", ["ICC2"], False)
    assert signed_out.get("/api/flights").status_code == 200


def test_reads_are_scoped_to_the_users_plants(signed_out, provider):
    sign_in(signed_out, provider, ["g-icc2"])
    airlines = {f["airline"] for f in signed_out.get("/api/flights").json()}
    assert "SQ" not in airlines and "QR" in airlines
    assert signed_out.get(SQ856_P06H).status_code == 403
    assert signed_out.get("/api/flights/SQ/856/2026-11-13/amf").status_code == 403
    assert signed_out.get(QR943_P24H).status_code == 200
    assert signed_out.get("/api/admin/airline-settings").status_code == 403


def test_admin_group_unlocks_admin_reads(signed_out, provider):
    sign_in(signed_out, provider, ["g-icc1", "g-admin"])
    assert signed_out.get("/api/admin/airline-settings").status_code == 200
    assert signed_out.get(SQ856_P06H).status_code == 200


def test_account_in_no_console_group_gets_no_session(signed_out, provider):
    assert sign_in(signed_out, provider, ["g-other"]).status_code == 403
    assert signed_out.get("/api/me").status_code == 401


def test_callback_refuses_unknown_state_and_replays(signed_out, provider):
    assert (
        signed_out.get("/auth/callback", params={"code": "x", "state": "nope"}).status_code == 401
    )
    provider.identities["c1"] = Identity("oid-1", frozenset(["g-icc1"]))
    state = signed_out.get("/auth/login").headers["location"].split("state=")[1]
    assert (
        signed_out.get("/auth/callback", params={"code": "bad", "state": state}).status_code == 401
    )
    # the flow is single use, even after a refusal
    assert (
        signed_out.get("/auth/callback", params={"code": "c1", "state": state}).status_code == 401
    )


def test_writes_need_the_csrf_token(signed_out, provider):
    sign_in(signed_out, provider, ["g-icc2"])
    url = f"{QR943_P24H}/review"
    assert signed_out.post(url).status_code == 403
    assert signed_out.post(url, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    token = signed_out.get("/api/me").json()["csrf_token"]
    assert signed_out.post(url, headers={"X-CSRF-Token": token}).status_code == 204


def test_logout_ends_the_session(signed_out, provider):
    sign_in(signed_out, provider, ["g-icc2"])
    token = signed_out.get("/api/me").json()["csrf_token"]
    assert signed_out.post("/auth/logout").status_code == 403  # no CSRF token
    assert signed_out.post("/auth/logout", headers={"X-CSRF-Token": token}).status_code == 204
    assert signed_out.get("/api/me").status_code == 401


def test_session_expires(engine, sender, provider):
    now = [0.0]
    store = InMemorySessionStore(clock=lambda: now[0])
    config = AuthConfig(provider, store, GROUPS, session_ttl_s=60, secure_cookie=False)
    client = TestClient(create_app(engine, sender, config), follow_redirects=False)
    sign_in(client, provider, ["g-icc1"])
    assert client.get("/api/me").status_code == 200
    now[0] = 61
    assert client.get("/api/me").status_code == 401


# --- Real adapters, with the network stubbed -------------------------------------------


def test_entra_provider_maps_claims_and_refuses_overage(monkeypatch):
    import app.adapters as adapters
    from app.adapters import EntraProvider

    # The real constructor fetches the tenant's OIDC metadata over the network.
    monkeypatch.setattr(adapters.msal, "ConfidentialClientApplication", lambda *a, **k: None)

    class StubApp:
        result: dict = {}

        def acquire_token_by_auth_code_flow(self, flow, params):
            return self.result

    provider = EntraProvider("tenant", "client", "secret", "http://localhost/auth/callback")
    provider._app = StubApp()
    provider._app.result = {"id_token_claims": {"oid": "o1", "groups": ["g-icc1"]}}
    assert provider.complete({}, {}) == Identity("o1", frozenset(["g-icc1"]))
    provider._app.result = {"id_token_claims": {"oid": "o1", "_claim_names": {"groups": "src1"}}}
    with pytest.raises(IdentityError, match="Too many groups"):
        provider.complete({}, {})
    provider._app.result = {"error": "invalid_grant", "error_description": "code expired"}
    with pytest.raises(IdentityError, match="code expired"):
        provider.complete({}, {})


def test_redis_store_namespaces_keys_and_sets_expiry():
    from app.adapters import RedisSessionStore

    class StubRedis:
        def __init__(self):
            self.data, self.ttl = {}, {}

        def set(self, key, value, ex):
            self.data[key], self.ttl[key] = value, ex

        def get(self, key):
            return self.data.get(key)

        def getdel(self, key):
            return self.data.pop(key, None)

        def delete(self, key):
            self.data.pop(key, None)

    stub = StubRedis()
    store = RedisSessionStore(stub)
    store.put("session:a", {"id": "o1"}, 60)
    assert list(stub.ttl.items()) == [("scat-console:session:a", 60)]
    assert store.get("session:a") == {"id": "o1"}
    assert store.pop("session:a") == {"id": "o1"} and store.pop("session:a") is None
    store.put("k", {}, 1)
    store.delete("k")
    assert store.get("k") is None


def test_email_list_is_scoped_to_the_users_plants(signed_out, provider):
    sign_in(signed_out, provider, ["g-icc2"])
    emails = signed_out.get("/api/emails").json()
    assert {e["airline"] for e in emails} == {"QR"}
    assert signed_out.get("/api/emails", params={"airline": "SQ"}).json() == []
    sign_in(signed_out, provider, ["g-icc1"], code="c2")
    assert {e["airline"] for e in signed_out.get("/api/emails").json()} == {"SQ"}


def test_audit_trail_is_scoped_to_the_users_plants(signed_out, provider):
    sign_in(signed_out, provider, ["g-icc2"])
    assert {e["airline"] for e in signed_out.get("/api/audit").json()} - {"SQ"}
    assert "SQ" not in {e["airline"] for e in signed_out.get("/api/audit").json()}
    assert signed_out.get("/api/audit", params={"airline": "SQ"}).json() == []
