"""SB-1283: every backend log line is one JSON object with request context.

Covers the access-log level mapping, the request line TraceMiddleware
writes (including an unhandled exception folded into it), and the filter
that stops uvicorn repeating a traceback we already logged.
"""

from __future__ import annotations

import io
import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from logging_config import DropAlreadyLoggedASGIException, setup_logging
from middleware.trace_middleware import TraceMiddleware, access_log_level


@pytest.mark.parametrize(
    ("status", "path", "level"),
    [
        (200, "/api/teams", logging.INFO),
        (304, "/api/teams", logging.INFO),
        (401, "/api/auth/login", logging.WARNING),
        (404, "/api/teams/9", logging.WARNING),
        (500, "/api/admin/attention/counts", logging.ERROR),
        (503, "/health", logging.ERROR),
        (200, "/health", logging.DEBUG),
        (200, "/metrics", logging.DEBUG),
    ],
)
def test_access_log_level(status, path, level):
    assert access_log_level(status, path) == level


@pytest.fixture
def client_and_logs():
    setup_logging(service_name="backend")
    # Read what the production handler renders, not pytest's log capture.
    stream = io.StringIO()
    logging.getLogger().handlers[0].setStream(stream)

    app = FastAPI()
    app.add_middleware(TraceMiddleware)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/missing")
    def missing():
        from fastapi import HTTPException

        raise HTTPException(status_code=404)

    @app.get("/boom")
    def boom():
        raise RuntimeError('relation "public.channel_requests" does not exist')

    def lines():
        return [json.loads(line) for line in stream.getvalue().splitlines()]

    return TestClient(app, raise_server_exceptions=False), lines


def _request_lines(lines):
    return [line for line in lines if line["event"] == "http_request"]


def test_success_is_one_info_json_line_with_request_id(client_and_logs):
    client, lines = client_and_logs
    resp = client.get("/ok", headers={"X-Request-ID": "mt-req-abc12345"})

    assert resp.headers["X-Request-ID"] == "mt-req-abc12345"
    [line] = _request_lines(lines())
    assert line["level"] == "info"
    assert line["status"] == 200
    assert line["path"] == "/ok"
    assert line["request_id"] == "mt-req-abc12345"


def test_4xx_is_warning(client_and_logs):
    client, lines = client_and_logs
    client.get("/missing")

    [line] = _request_lines(lines())
    assert line["level"] == "warning"
    assert line["status"] == 404


def test_unhandled_exception_is_one_error_line_with_cause(client_and_logs):
    client, lines = client_and_logs
    resp = client.get("/boom", headers={"X-Request-ID": "mt-req-boom0001"})

    assert resp.status_code == 500
    [line] = _request_lines(lines())
    assert line["level"] == "error"
    assert line["status"] == 500
    assert line["request_id"] == "mt-req-boom0001"
    # The cause travels in the same JSON line, not a separate raw traceback.
    assert 'relation \\"public.channel_requests\\" does not exist' in json.dumps(line["exception"])


def test_stdlib_loggers_render_as_json_with_context(client_and_logs):
    import structlog

    _, lines = client_and_logs
    structlog.contextvars.bind_contextvars(request_id="mt-req-std00001")
    try:
        logging.getLogger("uvicorn.error").error("plain stdlib message")
    finally:
        structlog.contextvars.unbind_contextvars("request_id")

    [line] = lines()
    assert line["event"] == "plain stdlib message"
    assert line["level"] == "error"
    assert line["request_id"] == "mt-req-std00001"


def _record(name, exc):
    return logging.LogRecord(
        name,
        logging.ERROR,
        __file__,
        1,
        "Exception in ASGI application",
        None,
        (type(exc), exc, None),
    )


def test_uvicorn_repeat_of_logged_exception_is_dropped():
    exc = RuntimeError("x")
    exc._mt_logged = True
    assert DropAlreadyLoggedASGIException().filter(_record("uvicorn.error", exc)) is False


def test_unlogged_exception_still_passes():
    f = DropAlreadyLoggedASGIException()
    assert f.filter(_record("uvicorn.error", RuntimeError("x"))) is True
    marked = RuntimeError("x")
    marked._mt_logged = True
    assert f.filter(_record("app", marked)) is True
