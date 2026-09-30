#!/usr/bin/env python3
"""API-only AI users (SB-1145): create them and mint their /api/ai/* tokens.

An API account is a user_profiles row with is_api_account=true. Prod requires
an auth.users row behind every profile (SB-1150), so each account has one with
no password, an undeliverable @missingtable.local email and a permanent ban:
it cannot log in to the web app. Its only credential is a short-lived token
this script mints, whose audience is accepted on /api/ai/* and rejected
everywhere else.

    APP_ENV=local uv run python scripts/manage_ai_users.py ensure
    APP_ENV=local uv run python scripts/manage_ai_users.py list
    APP_ENV=local uv run python scripts/manage_ai_users.py token ai_eval_real --out ~/.config/mt/ai_eval_real.local.jwt

Prod: run inside the backend pod, so the token is signed with the secret prod
actually verifies against, and redirect stdout to a file. `--out -` refuses to
write a token to a terminal, so it never lands in a transcript:

    kubectl exec deploy/missing-table-backend -n missing-table -- \\
        /app/.venv/bin/python scripts/manage_ai_users.py token ai_eval_real --out - \\
        > ~/.config/mt/ai_eval_real.prod.jwt
"""

import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth import AI_API_TOKEN_DEFAULT_DAYS, AI_API_TOKEN_MAX_DAYS, AuthManager, username_to_internal_email

app = typer.Typer(help=__doc__.split("\n")[0])

# Non-admin: an admin sees test data, which is exactly what the eval must not
# assume. team-fan is the default role and the least privileged.
API_ROLE = "team-fan"

# ~100 years. Supabase refuses sign-in and token refresh for a banned user; the
# /api/ai/* token is ours, not Supabase's, so the ban does not touch it.
PERMANENT_BAN = "876000h"


@dataclass(frozen=True)
class ApiAccount:
    username: str
    is_test: bool
    display_name: str


# ai_eval_real sees what a real fan sees; ai_eval_test also sees the TSC test
# world. Together they let an eval prove the partition in prod.
AI_EVAL_ACCOUNTS = (
    ApiAccount("ai_eval_real", is_test=False, display_name="MT AI eval (real viewer)"),
    ApiAccount("ai_eval_test", is_test=True, display_name="MT AI eval (test viewer)"),
)


def missing_accounts(existing_usernames: set[str]) -> list[ApiAccount]:
    return [a for a in AI_EVAL_ACCOUNTS if a.username not in existing_usernames]


def auth_user_attributes(account: ApiAccount) -> dict:
    """No password, no deliverable email, banned: nothing can sign in as this user."""
    return {
        "email": username_to_internal_email(account.username),
        "email_confirm": False,
        "ban_duration": PERMANENT_BAN,
        "user_metadata": {"display_name": account.display_name, "api_account": True},
    }


def profile_row(account: ApiAccount, user_id: str) -> dict:
    return {
        "id": user_id,
        "username": account.username,
        "display_name": account.display_name,
        "role": API_ROLE,
        "is_test": account.is_test,
        "is_api_account": True,
        "auth_provider": "api",
    }


def write_token(token: str, out: str, stdout_is_tty: bool) -> str:
    """Write the token to a 0600 file, or to stdout only when stdout is redirected."""
    if out == "-":
        if stdout_is_tty:
            raise typer.BadParameter("refusing to print a token to a terminal; redirect stdout to a file")
        sys.stdout.write(token + "\n")
        return "stdout"
    path = Path(out).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token + "\n")
    path.chmod(0o600)
    return str(path)


def create_api_account(client, account: ApiAccount) -> str:
    """Create the auth user, then upsert its profile; undo the auth user if that fails.

    Upsert, not insert: in prod the on_auth_user_created trigger has already
    made a bare team-fan profile for the new id. Locally there is no trigger.
    """
    user_id = str(client.auth.admin.create_user(auth_user_attributes(account)).user.id)
    try:
        client.table("user_profiles").upsert(profile_row(account, user_id)).execute()
    except Exception:
        client.auth.admin.delete_user(user_id)
        raise
    return user_id


def _client():
    load_dotenv()
    env_file = Path(__file__).resolve().parent.parent / f".env.{os.getenv('APP_ENV', 'local')}"
    if env_file.exists():
        load_dotenv(env_file, override=True)
    from supabase import create_client

    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _api_profiles(client) -> list[dict]:
    return (
        client.table("user_profiles")
        .select("id, username, role, is_test, is_api_account")
        .eq("is_api_account", True)
        .execute()
        .data
    )


def _err(message: str) -> None:
    # Status goes to stderr so `token --out -` leaves stdout holding the token alone.
    typer.echo(message, err=True)


@app.command()
def ensure() -> None:
    """Create the AI eval accounts that do not exist yet. Safe to re-run."""
    client = _client()
    taken = (
        client.table("user_profiles")
        .select("username, is_api_account")
        .in_("username", [a.username for a in AI_EVAL_ACCOUNTS])
        .execute()
        .data
    )
    clash = [r["username"] for r in taken if not r.get("is_api_account")]
    if clash:
        _err(f"username taken by a non-API account: {', '.join(clash)}")
        raise typer.Exit(1)
    for account in missing_accounts({r["username"] for r in taken}):
        user_id = create_api_account(client, account)
        _err(f"created {account.username} (is_test={account.is_test}) id={user_id}")
    _err(f"{os.getenv('APP_ENV', 'local')}: {len(AI_EVAL_ACCOUNTS)} AI eval accounts present")


@app.command("list")
def list_accounts() -> None:
    """List API accounts."""
    for row in _api_profiles(_client()):
        _err(f"{row['username']:<16} {row['role']:<10} is_test={row['is_test']}  id={row['id']}")


@app.command()
def token(
    username: str,
    out: str = typer.Option(..., help="File to write (0600), or '-' for redirected stdout."),
    days: int = typer.Option(AI_API_TOKEN_DEFAULT_DAYS, min=1, max=AI_API_TOKEN_MAX_DAYS),
) -> None:
    """Mint a short-lived /api/ai/* token for an API account."""
    client = _client()
    if not os.getenv("SERVICE_ACCOUNT_SECRET"):
        # AuthManager would fall back to a random secret: a token no server accepts.
        _err("SERVICE_ACCOUNT_SECRET is not set; the token would be unverifiable")
        raise typer.Exit(1)
    match = [r for r in _api_profiles(client) if r["username"] == username]
    if not match:
        _err(f"no API account named {username}; run `ensure` first")
        raise typer.Exit(1)
    minted = AuthManager(client).create_ai_api_token(match[0]["id"], expires_days=days)
    where = write_token(minted, out, sys.stdout.isatty())
    expires = (datetime.now(UTC) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M UTC")
    _err(f"token for {username} written to {where}; expires {expires}; valid on /api/ai/* only")


if __name__ == "__main__":
    app()
