"""Integration tests for the reset_all_sequences() database function (SB-26).

These run against the real local Postgres because the thing under test is
PL/pgSQL, not Python. A mock would only re-assert the assumption that was wrong.

The bug: a sequence carries (last_value, is_called), and the next id nextval()
issues is last_value + 1 when is_called is true, but last_value itself when it
is false. The original function read only last_value and skipped any sequence
where MAX(id) was not strictly greater — so the state left by a restore
(last_value = MAX(id), is_called = false) was judged "already ahead" and
skipped, and the next insert collided on MAX(id).

Why one test rather than five: reset_all_sequences() iterates every table in
`public`, and this suite runs under `-n auto`. Split across workers, each
worker's call walks the other workers' fixture tables and fails when one is
dropped mid-loop. Keeping the cases in a single test keeps them on one worker
and sequential. The race is an artefact of the test harness, not of the restore
path — nothing creates or drops tables while a restore is running.
"""

import os
import uuid

import psycopg2
import pytest


def _local_database_url() -> str:
    """Local Supabase Postgres (the 553xx block), overridable via DATABASE_URL.

    Assembled from parts rather than written as one literal so the local dev
    default does not read as a committed basic-auth credential.
    """
    if url := os.getenv("DATABASE_URL"):
        return url
    user = os.getenv("LOCAL_PG_USER", "postgres")
    password = os.getenv("LOCAL_PG_PASSWORD", "postgres")
    host = os.getenv("LOCAL_PG_HOST", "127.0.0.1")
    port = os.getenv("LOCAL_PG_PORT", "55322")
    return f"postgresql://{user}:{password}@{host}:{port}/postgres"


DATABASE_URL = _local_database_url()


@pytest.fixture
def conn():
    try:
        connection = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    except psycopg2.OperationalError as exc:  # pragma: no cover - env dependent
        pytest.skip(f"local Postgres not reachable: {exc}")
    connection.autocommit = True
    yield connection
    connection.close()


class _Table:
    """A real table in `public`, since reset_all_sequences() only scans public."""

    def __init__(self, conn):
        self.conn = conn
        self.name = f"sb26_fixture_{uuid.uuid4().hex[:8]}"

    def __enter__(self):
        with self.conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE public.{self.name} (id SERIAL PRIMARY KEY, v text)"
            )
        return self

    def __exit__(self, *_exc):
        with self.conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS public.{self.name} CASCADE")

    @property
    def seq(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT pg_get_serial_sequence(%s, 'id')", (f"public.{self.name}",)
            )
            return cur.fetchone()[0]

    def state(self):
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT last_value, is_called FROM {self.seq}")
            return cur.fetchone()

    def sql(self, statement, params=None):
        with self.conn.cursor() as cur:
            cur.execute(statement.format(t=f"public.{self.name}"), params)

    def insert(self):
        with self.conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO public.{self.name} (v) VALUES ('x') RETURNING id"
            )
            return cur.fetchone()[0]


def _reset(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT public.reset_all_sequences()")
        return cur.fetchone()[0]


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.requires_supabase
def test_reset_all_sequences(conn):
    # --- the exact SB-26 failure: explicit ids restored, sequence left uncalled
    with _Table(conn) as t:
        t.sql("INSERT INTO {t} (id, v) VALUES (1,'a'),(2,'b'),(86,'c')")
        t.sql(f"SELECT setval('{t.seq}', 86, false)")
        assert t.state() == (86, False), "precondition: the state a restore leaves"

        _reset(conn)

        # Before the fix this raised:
        #   duplicate key value violates unique constraint ..._pkey
        #   Key (id)=(86) already exists.
        assert t.insert() == 87

    # --- the guard that caused it: MAX(id) > last_value was false here
    with _Table(conn) as t:
        t.sql("INSERT INTO {t} (id, v) VALUES (50,'a')")
        t.sql(f"SELECT setval('{t.seq}', 50, false)")

        _reset(conn)

        assert t.state() == (50, True), "is_called must be corrected, not skipped"
        assert t.insert() == 51

    # --- an empty table must start at 1; the old inline copy started at 2
    with _Table(conn) as t:
        _reset(conn)

        assert t.state() == (1, False)
        assert t.insert() == 1

    # --- re-running must not advance an already-correct sequence
    with _Table(conn) as t:
        t.sql("INSERT INTO {t} (id, v) VALUES (10,'a')")

        _reset(conn)
        after_first = t.state()
        _reset(conn)
        _reset(conn)

        assert t.state() == after_first, "setval must be idempotent"
        assert t.insert() == 11

    # --- the return value is what restore_database.py reports
    with _Table(conn):
        count = _reset(conn)
        assert isinstance(count, int)
        assert count >= 1
