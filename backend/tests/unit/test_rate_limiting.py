"""Auth rate limiting (SB-640).

`RATE_LIMITS` used to describe a four-category policy while the middleware
and every decorator sat commented out, so login and signup were unthrottled
and the config read as if they were not. These tests pin the two things that
made enabling it risky, and would have caught either.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from rate_limiter import RATE_LIMITS, client_key, install_rate_limiting, rate_limit


@pytest.mark.unit
class TestTheKey:
    def _request(self, headers=None, host="10.0.0.1"):
        scope = {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
            "client": (host, 1234),
        }
        return Request(scope)

    def test_the_forwarded_client_is_the_bucket(self):
        # Behind the ingress every request arrives from one address. Keying
        # on the socket peer would put every user in the world into one
        # bucket, and five failed logins anywhere would lock out everyone.
        request = self._request({"x-forwarded-for": "203.0.113.7"}, host="10.0.0.1")
        assert client_key(request) == "203.0.113.7"

    def test_the_original_client_wins_over_the_proxy_chain(self):
        request = self._request({"x-forwarded-for": "203.0.113.7, 10.0.0.1"})
        assert client_key(request) == "203.0.113.7"

    def test_it_falls_back_to_the_peer_when_nothing_is_forwarded(self):
        assert client_key(self._request(host="198.51.100.4")) == "198.51.100.4"

    def test_a_client_that_cannot_be_identified_is_named_not_crashed(self):
        scope = {"type": "http", "headers": [], "client": None}
        assert client_key(Request(scope)) == "unknown"


@pytest.mark.unit
class TestEnforcement:
    @pytest.fixture(autouse=True)
    def fresh_counters(self):
        """The limiter is a module-level singleton, so its counters outlive a
        test. Reset around each one: a test that passes only when it runs
        first is worse than no test."""
        from rate_limiter import limiter as shared

        shared.reset()
        yield
        shared.reset()

    @pytest.fixture
    def client(self):
        app = FastAPI()
        install_rate_limiting(app)

        @app.post("/login")
        @rate_limit("5 per minute")
        async def login(request: Request):
            return {"ok": True}

        @app.get("/table")
        async def table(request: Request):
            return {"ok": True}

        return TestClient(app)

    def _post(self, client, ip):
        return client.post("/login", headers={"x-forwarded-for": ip})

    def test_the_sixth_attempt_in_a_minute_is_refused(self):
        app = FastAPI()
        install_rate_limiting(app)

        @app.post("/login")
        @rate_limit("5 per minute")
        async def login(request: Request):
            return {"ok": True}

        client = TestClient(app)
        codes = [self._post(client, "203.0.113.10").status_code for _ in range(6)]
        assert codes[:5] == [200] * 5
        assert codes[5] == 429

    def test_one_clients_attempts_do_not_lock_out_another(self, client):
        """The property that makes this safe to enable at all.

        Asserted as a relationship rather than against absolute counts: the
        limiter is a shared singleton, so a test that assumes it starts at
        zero passes or fails on execution order.
        """
        # Exhaust one client, however many that takes.
        for _ in range(20):
            if self._post(client, "203.0.113.20").status_code == 429:
                break
        else:
            pytest.fail("the limit never triggered")

        # A different household, mid-lockout, is unaffected. Behind the
        # ingress this is the difference between throttling an attacker and
        # locking out every user in the world.
        assert self._post(client, "203.0.113.21").status_code == 200

    def test_an_undecorated_endpoint_is_not_limited(self, client):
        # No global default limits: the LIVE tab polls and ingest posts in
        # bulk, and a blanket limit would read as an outage.
        for _ in range(50):
            assert client.get("/table", headers={"x-forwarded-for": "203.0.113.30"}).status_code == 200


@pytest.mark.unit
class TestTheConfigIsHonest:
    def test_every_configured_limit_is_one_that_is_applied(self):
        # The failure this module exists to prevent: config that describes
        # limits nothing enforces.
        assert set(RATE_LIMITS) == {"login", "signup", "password_reset"}

    def test_the_auth_routes_carry_a_limit(self):
        import app as app_module

        limited = {
            route.path
            for route in app_module.app.routes
            if getattr(route, "endpoint", None) and hasattr(route.endpoint, "__wrapped__")
        }
        for path in ("/api/auth/login", "/api/auth/signup", "/api/auth/forgot-password", "/api/auth/reset-password"):
            assert path in limited, f"{path} is not rate limited"
