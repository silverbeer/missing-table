"""mt-mcp served in-process for tests (SB-1302).

The real server, middleware, auth wiring and streamable-HTTP app run over an
ASGI transport — no socket, no Supabase. Only the token check is a fake: tokens
are looked up in a dict of user profiles shaped like auth_manager returns them.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mt_ai.tools import ToolDeps
from mt_mcp.auth import MTTokenVerifier
from mt_mcp.server import build_http_app, build_server

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer
    from starlette.applications import Starlette

BASE_URL = "http://127.0.0.1:8000"
URL = f"{BASE_URL}/"
ALLOWED_HOSTS = ["127.0.0.1:*", "localhost:*"]


def profile(user_id: str, role: str, **extra: Any) -> dict[str, Any]:
    return {"user_id": user_id, "username": user_id, "role": role, **extra}


# Session tokens → profiles. "api" is an API account (SB-1145), checked second.
SESSIONS = {
    "admin": profile("u-admin", "admin"),
    "club-mgr": profile("u-club", "club_manager", club_id=11),
    "team-mgr": profile("u-team", "team-manager", team_id=102, club_id=11),
    "player": profile("u-player", "team-player", team_id=102, club_id=11),
    "fan": profile("u-fan", "team-fan", team_id=102),
    "club-fan": profile("u-cfan", "club-fan", club_id=11),
    "test-fan": profile("u-tfan", "team-fan", is_test=True),
    "legacy": profile("u-legacy", "user"),
}
API_ACCOUNTS = {"api": profile("u-api", "team-fan", is_api_account=True)}


class FakeAuth:
    """Stands in for auth_manager.verify_token / verify_ai_api_token."""

    def __init__(self) -> None:
        self.seen: list[str] = []
        self.explode = False

    def verify_session(self, token: str) -> dict[str, Any] | None:
        self.seen.append(token)
        if self.explode:
            raise RuntimeError("profile lookup failed")
        return SESSIONS.get(token)

    def verify_api_account(self, token: str) -> dict[str, Any] | None:
        return API_ACCOUNTS.get(token)


class FakeIngest:
    """Stands in for IngestFailuresDAO: an in-memory ingest_failures table."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = {r["id"]: dict(r) for r in rows or []}
        self.fail = False
        self.resolve_calls: list[tuple[int, str | None, str | None]] = []

    def open_failures(self, since: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if self.fail:
            raise RuntimeError("PostgREST down")
        rows = [r for r in self.rows.values() if not r.get("resolved_at")]
        if since:
            rows = [r for r in rows if r["last_seen"] >= since]
        return sorted(rows, key=lambda r: r["last_seen"], reverse=True)[:limit]

    def get(self, failure_id: int) -> dict[str, Any] | None:
        if self.fail:
            raise RuntimeError("PostgREST down")
        row = self.rows.get(failure_id)
        return dict(row) if row else None

    def resolve_by_id(self, failure_id: int, *, resolved_by=None, note=None) -> dict[str, Any] | None:
        self.resolve_calls.append((failure_id, resolved_by, note))
        row = self.rows.get(failure_id)
        if row is None:
            return None
        if not row.get("resolved_at"):
            row.update(resolved_at="2026-10-10T12:00:00+00:00", resolved_by=resolved_by, resolution_note=note)
        return dict(row)


def failure_row(failure_id: int, raw_name: str, last_seen: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": failure_id,
        "kind": "team",
        "raw_name": raw_name,
        "league": "Homegrown",
        "source": "match-scraper",
        "match_count": 3,
        "sample": f"{raw_name} vs IFA",
        "first_seen": "2026-09-01T00:00:00+00:00",
        "last_seen": last_seen,
        "resolved_at": None,
        **extra,
    }


class Served:
    def __init__(self, deps: ToolDeps, ingest: FakeIngest | None = None) -> None:
        self.auth = FakeAuth()
        self.ingest = ingest or FakeIngest()
        self.deps = deps
        # What the tools call for their data; a test may swap it to simulate a crash.
        self.provide: Callable[[], ToolDeps] = lambda: self.deps
        self.server: MCPServer = build_server(
            MTTokenVerifier(self.auth.verify_session, self.auth.verify_api_account),
            lambda: self.provide(),
            issuer_url="http://127.0.0.1:55321/auth/v1",
            ingest=lambda: self.ingest,
        )
        self.app: Starlette = build_http_app(self.server, ALLOWED_HOSTS)

    def http(self, headers: dict[str, str] | None = None, **kwargs: Any) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=self.app), base_url=BASE_URL, headers=headers, **kwargs
        )

    def client_factory(self):
        """An ADK `httpx_client_factory` that reaches this app in-process."""

        def factory(headers=None, timeout=None, auth=None) -> httpx2.AsyncClient:
            return httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=self.app), headers=headers, timeout=timeout, auth=auth
            )

        return factory

    @asynccontextmanager
    async def session(self, token: str | None, client: str | None = None) -> AsyncIterator[ClientSession]:
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if client:
            headers["X-MT-Client"] = client
        async with (
            self.http(headers) as http,
            streamable_http_client(URL, http_client=http) as streams,
            ClientSession(streams[0], streams[1]) as session,
        ):
            await session.initialize()
            yield session


@asynccontextmanager
async def served(deps: ToolDeps, ingest: FakeIngest | None = None) -> AsyncIterator[Served]:
    s = Served(deps, ingest)
    async with s.server.session_manager.run():
        yield s


def initialize_body() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
    }


MCP_HEADERS = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
