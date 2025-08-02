#!/usr/bin/env python3
"""
End-to-end test for Supabase connection and data flow.
Tests: Connection → Data Access → API → CLI
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

console = Console()
load_dotenv()


def test_supabase_connection():
    """Test 1: Direct Supabase connection."""
    console.print("\n[bold cyan]Test 1: Direct Supabase Connection[/bold cyan]")

    try:
        from supabase import create_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        console.print(f"🔄 Connecting to: {url}")
        client = create_client(url, key)

        # Test basic query
        response = client.table("teams").select("*").limit(5).execute()

        console.print("✅ Connection successful!")
        console.print(f"✅ Found {len(response.data)} teams")

        if response.data:
            console.print(f"   Sample: {response.data[0]['name']}")

        return True

    except Exception as e:
        console.print(f"❌ Connection failed: {e}")
        return False


def test_enhanced_dao():
    """Test 2: Enhanced DAO layer."""
    console.print("\n[bold cyan]Test 2: Enhanced DAO Layer[/bold cyan]")

    try:
        from dao.enhanced_data_access import EnhancedSportsDAO, SupabaseConnection

        console.print("🔄 Initializing Enhanced DAO...")
        conn = SupabaseConnection()
        dao = EnhancedSportsDAO(conn)

        # Test getting teams
        teams = dao.get_all_teams()
        console.print(f"✅ DAO Teams: {len(teams)}")

        # Test getting games
        games = dao.get_all_games()
        console.print(f"✅ DAO Games: {len(games)}")

        # Test reference data
        seasons = dao.get_all_seasons()
        age_groups = dao.get_all_age_groups()
        game_types = dao.get_all_game_types()

        console.print(f"✅ Seasons: {len(seasons)}")
        console.print(f"✅ Age Groups: {len(age_groups)}")
        console.print(f"✅ Game Types: {len(game_types)}")

        return True

    except Exception as e:
        console.print(f"❌ DAO failed: {e}")
        return False


async def test_api_endpoints():
    """Test 3: API endpoints."""
    console.print("\n[bold cyan]Test 3: API Endpoints[/bold cyan]")

    api_base = "http://localhost:8000"

    async with httpx.AsyncClient(timeout=30.0) as client:
        endpoints = [
            ("/api/teams", "Teams"),
            ("/api/games", "Games"),
            ("/api/seasons", "Seasons"),
            ("/api/age-groups", "Age Groups"),
            ("/api/game-types", "Game Types"),
            ("/api/table", "League Table"),
        ]

        for endpoint, name in endpoints:
            try:
                response = await client.get(f"{api_base}{endpoint}")
                data = response.json()

                if isinstance(data, list):
                    console.print(f"✅ {name}: {len(data)} items")
                else:
                    console.print(f"✅ {name}: Response received")

            except Exception as e:
                console.print(f"❌ {name}: {str(e)[:50]}")
                return False

    return True


def test_cli_commands():
    """Test 4: CLI commands."""
    console.print("\n[bold cyan]Test 4: CLI Commands[/bold cyan]")

    import subprocess

    commands = [
        ("uv run mt-cli list-teams", "List Teams"),
        ("uv run mt-cli recent-games --limit 5", "Recent Games"),
        ("uv run mt-cli table", "League Table"),
    ]

    for cmd, name in commands:
        try:
            result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                console.print(f"✅ {name}: Success")
                # Show first few lines of output
                lines = result.stdout.strip().split("\n")[:3]
                for line in lines:
                    console.print(f"   {line[:80]}")
            else:
                console.print(f"❌ {name}: Failed")
                console.print(f"   Error: {result.stderr[:100]}")

        except subprocess.TimeoutExpired:
            console.print(f"❌ {name}: Timeout")
        except Exception as e:
            console.print(f"❌ {name}: {e}")


def main():
    """Run all E2E tests."""
    console.print("[bold green]🚀 End-to-End Supabase Test Suite[/bold green]")
    console.print("=" * 50)

    results = []

    # Test 1: Direct connection
    results.append(("Supabase Connection", test_supabase_connection()))

    # Test 2: DAO layer
    results.append(("Enhanced DAO", test_enhanced_dao()))

    # Test 3: API endpoints (check if server is running)
    console.print("\n[yellow]⚠️  Make sure the API server is running![/yellow]")
    console.print("Run: [cyan]uv run uvicorn app:app --reload[/cyan]")

    try:
        response = httpx.get("http://localhost:8000/api/teams", timeout=2.0)
        # API is running, test it
        results.append(("API Endpoints", asyncio.run(test_api_endpoints())))

        # Test 4: CLI commands
        results.append(("CLI Commands", test_cli_commands()))

    except:
        console.print("\n[red]❌ API server not running. Skipping API/CLI tests.[/red]")
        results.append(("API Endpoints", False))
        results.append(("CLI Commands", False))

    # Summary
    console.print("\n[bold green]📊 Test Summary[/bold green]")
    console.print("=" * 50)

    table = Table()
    table.add_column("Test", style="cyan")
    table.add_column("Status", style="green")

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        table.add_row(test_name, status)
        if not passed:
            all_passed = False

    console.print(table)

    if all_passed:
        console.print("\n[bold green]🎉 All tests passed! Supabase is working![/bold green]")
    else:
        console.print("\n[bold red]❌ Some tests failed. Check the errors above.[/bold red]")


if __name__ == "__main__":
    main()
