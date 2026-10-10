"""mt-mcp configuration, all from the environment (SB-1302).

MT_MCP_ENABLED=true             mount /mcp, and let MT AI call it (default off)
MT_MCP_INTERNAL_URL=...         how MT AI reaches it: loopback into this process
MT_MCP_ALLOWED_HOSTS=a,b        Host headers accepted besides loopback
"""

import os

MOUNT_PATH = "/mcp"

# Loopback is always allowed (MT AI's own calls); public names come from config.
LOOPBACK_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*", "127.0.0.1", "localhost"]
DEFAULT_PUBLIC_HOSTS = "api.missingtable.com"


def mcp_enabled() -> bool:
    return os.getenv("MT_MCP_ENABLED", "false").strip().lower() == "true"


def internal_url() -> str:
    # The trailing slash is the mount's own route; without it Starlette redirects.
    return os.getenv("MT_MCP_INTERNAL_URL", f"http://127.0.0.1:8000{MOUNT_PATH}/")


def allowed_hosts() -> list[str]:
    raw = os.getenv("MT_MCP_ALLOWED_HOSTS", DEFAULT_PUBLIC_HOSTS)
    return LOOPBACK_HOSTS + [h.strip() for h in raw.split(",") if h.strip()]


def issuer_url() -> str:
    """Where MT's tokens come from: Supabase auth. Advertised, never contacted."""
    return os.getenv("SUPABASE_URL", "http://127.0.0.1:55321").rstrip("/") + "/auth/v1"
