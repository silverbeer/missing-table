#!/usr/bin/env python
"""
Cache inspection CLI tool.

A command-line tool for inspecting and managing the Redis cache.

Usage:
    uv run python cache_cli.py --help
    uv run python cache_cli.py list
    uv run python cache_cli.py stats
    uv run python cache_cli.py get mt:teams:all
    uv run python cache_cli.py delete mt:teams:all
    uv run python cache_cli.py flush
"""

import json
import os
from datetime import datetime

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

app = typer.Typer(
    name="cache-cli",
    help="Inspect and manage the Redis cache for MissingTable",
    add_completion=False,
)
console = Console()


def get_redis_source():
    """Read Redis source info from .mt-config."""
    config_path = os.path.join(os.path.dirname(__file__), "..", ".mt-config")
    config = {}
    try:
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key] = value
    except FileNotFoundError:
        pass
    source = config.get("redis_source", "local")
    if source == "cloud":
        context = config.get("cloud_context", "not configured")
        return f"cloud ({context})"
    return f"local ({config.get('local_context', 'rancher-desktop')})"


def get_redis_client():
    """Get Redis client from environment or default."""
    import redis

    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis.from_url(url, decode_responses=True)
        client.ping()
        console.print(f"[dim]Redis: {get_redis_source()} ({url})[/dim]")
        return client
    except redis.RedisError as e:
        console.print(f"[red]Error connecting to Redis:[/red] {e}")
        console.print(f"[dim]URL: {url}[/dim]")
        console.print(f"[dim]Configured source: {get_redis_source()}[/dim]")
        raise typer.Exit(1) from None


def format_bytes(size: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_ttl(ttl: int) -> str:
    """Format TTL into human-readable string."""
    if ttl == -1:
        return "[dim]no expiry[/dim]"
    if ttl == -2:
        return "[red]expired[/red]"
    if ttl < 60:
        return f"{ttl}s"
    if ttl < 3600:
        return f"{ttl // 60}m {ttl % 60}s"
    return f"{ttl // 3600}h {(ttl % 3600) // 60}m"


@app.command(name="list")
def list_keys(
    pattern: str = typer.Option("mt:*", "--pattern", "-p", help="Key pattern to match"),
    show_ttl: bool = typer.Option(True, "--ttl/--no-ttl", help="Show TTL for each key"),
    show_size: bool = typer.Option(True, "--size/--no-size", help="Show size for each key"),
):
    """List all cache keys matching a pattern."""
    r = get_redis_client()

    keys = list(r.scan_iter(pattern))

    if not keys:
        console.print(f"[yellow]No keys found matching pattern:[/yellow] {pattern}")
        raise typer.Exit(0)

    table = Table(title=f"Cache Keys ({len(keys)} total)", box=box.ROUNDED)
    table.add_column("Key", style="cyan", no_wrap=True, overflow="fold")
    if show_ttl:
        table.add_column("TTL", justify="right")
    if show_size:
        table.add_column("Size", justify="right")
    table.add_column("Type", style="dim")

    for key in sorted(keys):
        # Use Text object to prevent Rich markup/emoji interpretation
        key_text = Text(key, style="cyan")
        row = [key_text]

        if show_ttl:
            ttl = r.ttl(key)
            row.append(format_ttl(ttl))

        if show_size:
            try:
                size = r.memory_usage(key) or 0
                row.append(format_bytes(size))
            except Exception:
                row.append("[dim]n/a[/dim]")

        key_type = r.type(key)
        row.append(key_type)

        table.add_row(*row)

    console.print(table)


@app.command()
def stats():
    """Show cache statistics."""
    r = get_redis_client()

    # Get all keys with our prefix
    prefix = os.getenv("CACHE_KEY_PREFIX", "mt")
    keys = list(r.scan_iter(f"{prefix}:*"))

    # Calculate stats
    total_size = 0
    by_domain = {}

    for key in keys:
        try:
            size = r.memory_usage(key) or 0
            total_size += size
        except Exception:
            size = 0

        # Extract domain from key (e.g., "mt:clubs:all" -> "clubs")
        parts = key.split(":")
        if len(parts) >= 2:
            domain = parts[1]
            if domain not in by_domain:
                by_domain[domain] = {"count": 0, "size": 0}
            by_domain[domain]["count"] += 1
            by_domain[domain]["size"] += size

    # Get Redis info
    info = r.info("memory")

    # Build stats panel
    stats_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    stats_table.add_column("Metric", style="bold")
    stats_table.add_column("Value", style="cyan")

    stats_table.add_row("Total Keys", str(len(keys)))
    stats_table.add_row("Cache Size", format_bytes(total_size))
    stats_table.add_row("Redis Memory", format_bytes(info.get("used_memory", 0)))
    stats_table.add_row("Peak Memory", format_bytes(info.get("used_memory_peak", 0)))

    console.print(Panel(stats_table, title="Cache Statistics", border_style="blue"))

    # Domain breakdown
    if by_domain:
        domain_table = Table(title="By Domain", box=box.ROUNDED)
        domain_table.add_column("Domain", style="cyan")
        domain_table.add_column("Keys", justify="right")
        domain_table.add_column("Size", justify="right")

        for domain, data in sorted(by_domain.items()):
            domain_table.add_row(
                domain,
                str(data["count"]),
                format_bytes(data["size"]),
            )

        console.print(domain_table)


@app.command()
def get(
    key: str = typer.Argument(..., help="Cache key to retrieve"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Output raw JSON without formatting"),
):
    """Get and display a cached value."""
    r = get_redis_client()

    if not r.exists(key):
        console.print(f"[red]Key not found:[/red] {key}")
        raise typer.Exit(1)

    key_type = r.type(key)
    ttl = r.ttl(key)

    if key_type == "string":
        value = r.get(key)
        try:
            data = json.loads(value)
            if raw:
                console.print_json(json.dumps(data))
            else:
                # Show metadata
                meta_table = Table(box=box.SIMPLE, show_header=False)
                meta_table.add_column("", style="bold")
                meta_table.add_column("")
                meta_table.add_row("Key", Text(key, style="cyan"))
                meta_table.add_row("TTL", format_ttl(ttl))
                meta_table.add_row("Type", key_type)

                if isinstance(data, list):
                    meta_table.add_row("Items", str(len(data)))
                    console.print(Panel(meta_table, title="Cache Entry", border_style="green"))

                    # Show preview of list items
                    if data:
                        preview_table = Table(
                            title=f"Data Preview (first 5 of {len(data)})",
                            box=box.ROUNDED,
                        )

                        # Use first item to determine columns
                        if isinstance(data[0], dict):
                            # Show select columns for readability
                            cols = list(data[0].keys())[:6]
                            for col in cols:
                                preview_table.add_column(col, overflow="ellipsis", max_width=20)

                            for item in data[:5]:
                                row = [str(item.get(col, ""))[:20] for col in cols]
                                preview_table.add_row(*row)
                        else:
                            preview_table.add_column("Value")
                            for item in data[:5]:
                                preview_table.add_row(str(item)[:50])

                        console.print(preview_table)

                elif isinstance(data, dict):
                    meta_table.add_row("Fields", str(len(data)))
                    console.print(Panel(meta_table, title="Cache Entry", border_style="green"))

                    # Show dict contents
                    tree = Tree(Text(key, style="bold"))
                    for k, v in list(data.items())[:20]:
                        if isinstance(v, dict | list):
                            tree.add(f"[cyan]{k}[/cyan]: [dim]{type(v).__name__}[/dim]")
                        else:
                            tree.add(f"[cyan]{k}[/cyan]: {str(v)[:50]}")
                    console.print(tree)
                else:
                    console.print(Panel(meta_table, title="Cache Entry", border_style="green"))
                    console.print(data)

        except json.JSONDecodeError:
            console.print("[yellow]Raw string value:[/yellow]")
            console.print(value[:500])
    else:
        console.print(f"[yellow]Unsupported type:[/yellow] {key_type}")


@app.command()
def delete(
    pattern: str = typer.Argument(..., help="Key or pattern to delete (use * for wildcards)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete cache keys matching a pattern."""
    r = get_redis_client()

    keys = list(r.scan_iter(pattern)) if "*" in pattern else ([pattern] if r.exists(pattern) else [])

    if not keys:
        console.print(f"[yellow]No keys found matching:[/yellow] {pattern}")
        raise typer.Exit(0)

    # Show keys to be deleted
    console.print(f"[bold]Keys to delete ({len(keys)}):[/bold]")
    for key in keys[:10]:
        console.print(f"  [red]- {key}[/red]")
    if len(keys) > 10:
        console.print(f"  [dim]... and {len(keys) - 10} more[/dim]")

    if not force:
        confirm = typer.confirm(f"Delete {len(keys)} key(s)?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(0)

    # Delete keys
    deleted = r.delete(*keys)
    console.print(f"[green]Deleted {deleted} key(s)[/green]")


@app.command()
def flush(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Flush all cache keys with our prefix."""
    r = get_redis_client()

    prefix = os.getenv("CACHE_KEY_PREFIX", "mt")
    pattern = f"{prefix}:*"
    keys = list(r.scan_iter(pattern))

    if not keys:
        console.print("[yellow]Cache is already empty[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold red]This will delete {len(keys)} cache keys![/bold red]")

    if not force:
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(0)

    deleted = r.delete(*keys)
    console.print(f"[green]Flushed {deleted} key(s)[/green]")


@app.command()
def monitor(
    duration: int = typer.Option(10, "--duration", "-d", help="Duration in seconds"),
):
    """Monitor cache operations in real-time."""
    r = get_redis_client()

    console.print(f"[bold]Monitoring Redis commands for {duration} seconds...[/bold]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        pubsub = r.pubsub()
        # Note: MONITOR is not available via pubsub, using keyspace notifications instead
        r.config_set("notify-keyspace-events", "KEA")

        prefix = os.getenv("CACHE_KEY_PREFIX", "mt")
        pubsub.psubscribe(f"__keyspace@0__:{prefix}:*")

        import time

        start = time.time()
        while time.time() - start < duration:
            message = pubsub.get_message(timeout=1.0)
            if message and message["type"] == "pmessage":
                channel = message["channel"]
                operation = message["data"]
                key = channel.split(":", 1)[1] if ":" in channel else channel

                color = {
                    "set": "green",
                    "del": "red",
                    "expire": "yellow",
                    "get": "cyan",
                }.get(operation, "white")

                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                console.print(f"[dim]{timestamp}[/dim] [{color}]{operation:6}[/{color}] {key}")

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped monitoring[/dim]")
    finally:
        pubsub.close()


if __name__ == "__main__":
    app()
