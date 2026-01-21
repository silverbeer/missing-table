#!/usr/bin/env python3
"""
Connection Diagnostic Tool

Diagnoses connection issues with Supabase environments.
Validates URL format, tests connectivity, and checks credentials format.
"""

import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer()
console = Console()


def load_env_file(env: str) -> dict:
    """Load environment variables from .env.{env} file."""
    env_file = Path(__file__).parent.parent / f".env.{env}"

    if not env_file.exists():
        console.print(f"[red]Error: {env_file} not found[/red]")
        return {}

    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                value = value.strip().strip('"').strip("'")
                env_vars[key.strip()] = value

    return env_vars


def mask_credential(credential: str, show_chars: int = 8) -> str:
    """Mask credential but show first and last few chars for validation."""
    if not credential or len(credential) < show_chars * 2:
        return "[too short or empty]"

    return f"{credential[:show_chars]}...{credential[-show_chars:]}"


def validate_url(url: str) -> tuple[bool, str]:
    """Validate Supabase URL format."""
    if not url:
        return False, "URL is empty"

    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ["http", "https"]:
            return False, f"Invalid scheme: {parsed.scheme} (should be https)"

        # Check if hostname exists
        if not parsed.netloc:
            return False, "No hostname found in URL"

        # Supabase URLs should be HTTPS
        if parsed.scheme != "https":
            return False, "Supabase URLs should use HTTPS"

        # Check if it looks like a Supabase URL
        if "supabase" not in parsed.netloc.lower():
            return False, f"URL doesn't look like Supabase: {parsed.netloc}"

        return True, f"Valid format: {parsed.scheme}://{parsed.netloc}"

    except Exception as e:
        return False, f"Parse error: {e!s}"


def test_dns_resolution(url: str) -> tuple[bool, str]:
    """Test if hostname can be resolved."""
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc

        # Remove port if present
        if ":" in hostname:
            hostname = hostname.split(":")[0]

        # Try to resolve hostname
        ip_address = socket.gethostbyname(hostname)
        return True, f"Resolves to: {ip_address}"

    except socket.gaierror as e:
        return False, f"DNS resolution failed: {e!s}"
    except Exception as e:
        return False, f"Error: {e!s}"


def test_connectivity(url: str, timeout: int = 5) -> tuple[bool, str]:
    """Test if URL is reachable."""
    try:
        import urllib.request

        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        response = urllib.request.urlopen(request, timeout=timeout)

        return True, f"HTTP {response.status} - {response.reason}"

    except urllib.error.HTTPError as e:
        # HTTP errors mean we connected (good), just got an error response
        return True, f"Connected but got HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"Connection failed: {e.reason!s}"
    except Exception as e:
        return False, f"Error: {e!s}"


@app.command()
def diagnose(
    env: str = typer.Argument("prod", help="Environment to diagnose (local, dev, prod)"),
    test_connection: bool = typer.Option(True, "--test/--no-test", help="Test actual connectivity"),
):
    """Diagnose connection issues with Supabase environment."""

    console.print(Panel.fit(f"[bold cyan]Connection Diagnostic: {env.upper()}[/bold cyan]", box=box.DOUBLE))

    # Load environment variables
    console.print(f"\n[bold]Loading {env} environment...[/bold]")
    env_vars = load_env_file(env)

    if not env_vars:
        console.print("[red]Failed to load environment file[/red]")
        return

    # Get credentials
    supabase_url = env_vars.get("SUPABASE_URL", "")
    supabase_key = (
        env_vars.get("SUPABASE_SERVICE_ROLE_KEY")
        or env_vars.get("SUPABASE_SERVICE_KEY")
        or env_vars.get("SUPABASE_KEY")
    )

    # Create results table
    table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    # Check 1: URL exists
    if supabase_url:
        table.add_row("SUPABASE_URL present", "[green]✓[/green]", mask_credential(supabase_url, 20))
    else:
        table.add_row("SUPABASE_URL present", "[red]✗[/red]", "Missing or empty")

    # Check 2: Key exists
    if supabase_key:
        table.add_row("Service key present", "[green]✓[/green]", mask_credential(supabase_key, 8))
    else:
        table.add_row("Service key present", "[red]✗[/red]", "Missing or empty")

    # Check 3: URL format validation
    if supabase_url:
        valid, message = validate_url(supabase_url)
        table.add_row("URL format valid", "[green]✓[/green]" if valid else "[red]✗[/red]", message)

        # Check 4: DNS resolution
        if valid:
            can_resolve, resolve_msg = test_dns_resolution(supabase_url)
            table.add_row("DNS resolution", "[green]✓[/green]" if can_resolve else "[red]✗[/red]", resolve_msg)

            # Check 5: Connectivity test (optional)
            if test_connection and can_resolve:
                console.print(table)
                console.print("\n[yellow]Testing connectivity (this may take a few seconds)...[/yellow]")
                can_connect, connect_msg = test_connectivity(supabase_url)

                # Create new table with connectivity result
                table.add_row(
                    "HTTP connectivity",
                    "[green]✓[/green]" if can_connect else "[red]✗[/red]",
                    connect_msg,
                )

    console.print(table)

    # Recommendations
    console.print("\n[bold]Recommendations:[/bold]")

    if not supabase_url:
        console.print("[red]• Add SUPABASE_URL to .env.{env}[/red]")
    elif not supabase_key:
        console.print("[red]• Add service key to .env.{env}[/red]")
    else:
        valid, message = validate_url(supabase_url)
        if not valid:
            console.print(f"[red]• Fix SUPABASE_URL format: {message}[/red]")
        else:
            can_resolve, resolve_msg = test_dns_resolution(supabase_url)
            if not can_resolve:
                console.print(f"[red]• DNS issue: {resolve_msg}[/red]")
                console.print("[yellow]  - Check if the URL is correct[/yellow]")
                console.print("[yellow]  - Verify network connectivity[/yellow]")
                console.print("[yellow]  - Try pinging the hostname manually[/yellow]")
            else:
                console.print("[green]• Configuration looks good![/green]")

                if test_connection:
                    can_connect, connect_msg = test_connectivity(supabase_url)
                    if not can_connect:
                        console.print(f"[yellow]• Connectivity issue: {connect_msg}[/yellow]")
                        console.print("[yellow]  - Check firewall settings[/yellow]")
                        console.print("[yellow]  - Verify Supabase project is active[/yellow]")

    # Manual testing suggestions
    console.print("\n[bold]Manual Testing:[/bold]")
    if supabase_url:
        parsed = urlparse(supabase_url)
        hostname = parsed.netloc.split(":")[0] if ":" in parsed.netloc else parsed.netloc

        console.print("Test DNS resolution:")
        console.print(f"  [cyan]nslookup {hostname}[/cyan]")
        console.print("\nTest connectivity:")
        console.print(f"  [cyan]curl -I {supabase_url}[/cyan]")
        console.print("\nTest with Python:")
        console.print(f"  [cyan]python3 -c \"import socket; print(socket.gethostbyname('{hostname}'))\"[/cyan]")


if __name__ == "__main__":
    app()
