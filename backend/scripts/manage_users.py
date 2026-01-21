#!/usr/bin/env python3
"""
Comprehensive user management script for Supabase environments.
Supports password changes, user creation, role management, and user info.
"""

import os
import secrets
import string

import typer
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from supabase import create_client

app = typer.Typer()
console = Console()

# Valid roles matching the database constraint (user_profiles_role_check)
VALID_ROLES = {
    "admin",
    "club_manager",
    "club-manager",
    "club_fan",
    "club-fan",
    "team_manager",
    "team-manager",
    "team_player",
    "team-player",
    "team_fan",
    "team-fan",
}


def validate_role(role: str) -> tuple[bool, str]:
    """
    Validate a role against the database constraint.
    Returns (is_valid, error_message).
    """
    if role in VALID_ROLES:
        return True, ""

    # Try to suggest a correction
    suggestions = []
    role_lower = role.lower()
    for valid_role in VALID_ROLES:
        # Check for common typos using simple edit distance approximation
        if role_lower in valid_role or valid_role in role_lower:
            suggestions.append(valid_role)
        # Check if only 1-2 chars different
        elif len(role) == len(valid_role):
            diff = sum(1 for a, b in zip(role_lower, valid_role, strict=False) if a != b)
            if diff <= 2:
                suggestions.append(valid_role)

    # Deduplicate and format suggestions
    suggestions = list(set(suggestions))

    error_msg = f"Invalid role: '{role}'"
    if suggestions:
        error_msg += f"\n  Did you mean: {', '.join(suggestions)}?"
    error_msg += f"\n  Valid roles: {', '.join(sorted(VALID_ROLES))}"

    return False, error_msg


def load_environment():
    """Load environment variables based on APP_ENV or default to dev."""
    load_dotenv()
    app_env = os.getenv("APP_ENV", "dev")
    env_file = f".env.{app_env}"
    if os.path.exists(env_file):
        load_dotenv(env_file, override=True)
    else:
        pass


def find_user_by_identifier(supabase, identifier):
    """
    Find a user by email or username.
    Returns (user_id, identifier_used, identifier_type) or (None, None, None) if not found.
    """
    # Check if identifier looks like email or username
    if "@" in identifier and not identifier.endswith("@missingtable.local"):
        # Real email - search in auth.users
        response = supabase.auth.admin.list_users()
        users_list = response if isinstance(response, list) else getattr(response, "data", {}).get("users", [])

        for user in users_list:
            user_email = user.email if hasattr(user, "email") else user.get("email")
            if user_email == identifier:
                user_id = user.id if hasattr(user, "id") else user.get("id")
                return (user_id, identifier, "email")
        return (None, None, None)
    else:
        # Username or internal email - search in user_profiles first
        profile_response = (
            supabase.table("user_profiles").select("id, username, display_name").eq("username", identifier).execute()
        )

        if profile_response.data:
            user_id = profile_response.data[0]["id"]
            username = profile_response.data[0]["username"]
            return (user_id, username, "username")

        # If not found by username, try as internal email in auth.users
        internal_email = identifier if "@missingtable.local" in identifier else f"{identifier}@missingtable.local"
        response = supabase.auth.admin.list_users()
        users_list = response if isinstance(response, list) else getattr(response, "data", {}).get("users", [])

        for user in users_list:
            user_email = user.email if hasattr(user, "email") else user.get("email")
            if user_email == internal_email:
                user_id = user.id if hasattr(user, "id") else user.get("id")
                return (user_id, internal_email, "internal_email")

        return (None, None, None)


def generate_secure_password(length=12):
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = "".join(secrets.choice(alphabet) for i in range(length))
    return password


def get_supabase_client():
    """Create Supabase client with service key."""
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not service_key:
        console.print("[red]❌ Error: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY[/red]")
        return None

    return create_client(supabase_url, service_key)


def list_users(supabase):
    """List all users in the system."""
    try:
        console.print("📋 Fetching all users...")

        # Get users from auth.users
        response = supabase.auth.admin.list_users()
        users_list = response if isinstance(response, list) else getattr(response, "data", {}).get("users", [])

        if not users_list:
            console.print("[yellow]No users found[/yellow]")
            return True

        console.print(f"\n[bold cyan]👥 Found {len(users_list)} users:[/bold cyan]")

        # Create a rich table for better display with row separators
        table = Table(
            show_header=True,
            header_style="bold magenta",
            show_lines=True,  # Show lines between rows
            box=box.ROUNDED,  # Rounded box with borders and lighter row separators
            row_styles=["", "dim"],  # Alternate row styling for better readability
            width=150,  # Set reasonable max width
        )
        table.add_column("Username/Email", style="green", max_width=25)
        table.add_column("ID", style="dim", max_width=12, overflow="ellipsis")  # Truncate UUID
        table.add_column("Role", style="yellow", max_width=15)
        table.add_column("Display Name", style="cyan", max_width=20)
        table.add_column("Team", style="blue", max_width=25)
        table.add_column("Created", style="dim", max_width=10, no_wrap=True)

        for user in users_list:
            user_id = user.id if hasattr(user, "id") else user.get("id")
            auth_email = user.email if hasattr(user, "email") else user.get("email")
            created_at = user.created_at if hasattr(user, "created_at") else user.get("created_at")

            # Get profile info with team details
            try:
                # Try to select email column, but it might not exist in all schemas
                profile_result = (
                    supabase.table("user_profiles")
                    .select("username, role, display_name, team_id, teams(id, name)")
                    .eq("id", user_id)
                    .execute()
                )
                if profile_result.data:
                    profile = profile_result.data[0]
                    username = profile.get("username", "N/A")
                    role = profile.get("role", "No role")
                    display_name = profile.get("display_name", "No display name")
                    team_id = profile.get("team_id")

                    # Determine identifier to show (username > email > auth_email)
                    # Username authentication users will have username field
                    # Legacy email users will have email in auth but not username
                    if username and username != "N/A":
                        identifier = username
                    elif profile.get("email"):
                        identifier = profile.get("email")
                    else:
                        # Fallback to auth email (might be internal format like user@missingtable.local)
                        identifier = (
                            auth_email if auth_email and not auth_email.endswith("@missingtable.local") else "N/A"
                        )

                    # Format team display (ID + Name for team-manager/team-player/team-fan)
                    if team_id and profile.get("teams"):
                        team_name = profile["teams"].get("name", "Unknown")
                        team_display = f"[{team_id}] {team_name}"
                    elif team_id:
                        team_display = f"[{team_id}] (name unknown)"
                    else:
                        team_display = "No team"
                else:
                    identifier = auth_email if auth_email else "N/A"
                    role = display_name = team_display = "No profile"
            except Exception as e:
                identifier = auth_email if auth_email else "N/A"
                role = display_name = team_display = f"Error: {str(e)[:30]}"

            # Color code roles
            if role == "admin":
                role_display = f"[bold red]{role}[/bold red]"
            elif role == "team-manager":
                role_display = f"[bold yellow]{role}[/bold yellow]"
            elif role == "team-player":
                role_display = f"[bold blue]{role}[/bold blue]"
            elif role == "team-fan":
                role_display = f"[bold green]{role}[/bold green]"
            else:
                role_display = role

            table.add_row(
                identifier or "N/A",
                user_id[:8] if user_id else "N/A",  # Show first 8 chars of UUID
                role_display,
                display_name,
                team_display,
                str(created_at)[:10] if created_at else "Unknown",
            )

        console.print(table)
        return True

    except Exception as e:
        console.print(f"[red]❌ Error listing users: {e}[/red]")
        return False


def change_password(supabase, email, new_password=None, generate=False):
    """Change a user's password."""
    try:
        # Find user by email
        response = supabase.auth.admin.list_users()
        users_list = response if isinstance(response, list) else getattr(response, "data", {}).get("users", [])

        user_found = None
        for user in users_list:
            user_email = user.email if hasattr(user, "email") else user.get("email")
            if user_email == email:
                user_found = user
                break

        if not user_found:
            return False

        user_id = user_found.id if hasattr(user_found, "id") else user_found.get("id")

        # Handle password
        if generate:
            new_password = generate_secure_password()
        elif not new_password:
            new_password = Prompt.ask("Enter new password", password=True)
            if not new_password:
                console.print("[red]❌ Password cannot be empty[/red]")
                return False

        # Reset password using admin API

        reset_response = supabase.auth.admin.update_user_by_id(user_id, {"password": new_password})

        if reset_response.user:
            if generate:
                pass
            return True
        else:
            return False

    except Exception:
        return False


def create_user(supabase, email, password=None, role="user", display_name=None, generate=False, club_id=None):
    """Create a new user."""
    try:
        # Handle password
        if generate:
            password = generate_secure_password()
        elif not password:
            password = Prompt.ask("Enter password for new user", password=True)
            if not password:
                console.print("[red]❌ Password cannot be empty[/red]")
                return False

        if not display_name:
            display_name = email.split("@")[0]

        # Create user using admin API
        create_response = supabase.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,  # Auto-confirm email
            }
        )

        if create_response.user:
            user_id = create_response.user.id

            # Extract username from email (e.g., "e2e_admin" from "e2e_admin@missingtable.local")
            username = email.split("@")[0]

            # Create user profile
            profile_data = {
                "id": user_id,
                "username": username,
                "role": role,
                "display_name": display_name,
            }

            # Add club_id if provided (for club_manager role)
            if club_id:
                profile_data["club_id"] = club_id

            profile_response = supabase.table("user_profiles").insert(profile_data).execute()

            if profile_response.data:
                pass
            else:
                pass

            if generate:
                pass

            if club_id:
                pass

            return True
        else:
            return False

    except Exception:
        return False


def update_user_role(supabase, identifier, new_role):
    """Update a user's role (accepts username or email)."""
    try:
        console.print(f"[cyan]🔍 Looking up user: {identifier}[/cyan]")

        # Find user by username or email
        user_id, found_identifier, id_type = find_user_by_identifier(supabase, identifier)

        if not user_id:
            console.print(f"[red]❌ User '{identifier}' not found[/red]")
            console.print("[yellow]💡 Hint: Use 'manage_users.py list' to see all users[/yellow]")
            return False

        console.print(f"[green]✓ Found user: {found_identifier} (via {id_type})[/green]")

        # Check if profile exists
        profile_check = supabase.table("user_profiles").select("*").eq("id", user_id).execute()

        if not profile_check.data:
            # Profile doesn't exist, create it
            console.print("[yellow]⚠️  No profile found, creating one...[/yellow]")

            # Extract username from identifier if possible
            if id_type == "username":
                username = found_identifier
            elif "@missingtable.local" in found_identifier:
                username = found_identifier.replace("@missingtable.local", "")
            else:
                username = found_identifier.split("@")[0]

            profile_data = {
                "id": user_id,
                "role": new_role,
                "username": username,
                "display_name": username.title(),
            }

            create_response = supabase.table("user_profiles").insert(profile_data).execute()

            if create_response.data:
                console.print("\n[bold green]✅ Profile created and role set successfully![/bold green]")
                console.print(f"  User: [cyan]{username}[/cyan]")
                console.print(f"  Role: [yellow]{new_role}[/yellow]")
                return True
            else:
                console.print("[red]❌ Failed to create profile[/red]")
                return False

        # Update role in user_profiles
        update_response = supabase.table("user_profiles").update({"role": new_role}).eq("id", user_id).execute()

        if update_response.data:
            console.print("\n[bold green]✅ Role updated successfully![/bold green]")
            console.print(f"  User: [cyan]{found_identifier}[/cyan]")
            console.print(f"  New role: [yellow]{new_role}[/yellow]")
            return True
        else:
            console.print("[red]❌ Role update failed[/red]")
            return False

    except Exception as e:
        console.print(f"[red]❌ Error updating role: {e}[/red]")
        return False


def update_user_team(supabase, identifier, team_id):
    """Update a user's team assignment."""
    try:
        console.print(f"[cyan]🔍 Looking up user: {identifier}[/cyan]")

        # Check if identifier looks like email or username
        if "@" in identifier:
            # Search by email
            response = supabase.auth.admin.list_users()
            users_list = response if isinstance(response, list) else getattr(response, "data", {}).get("users", [])

            user_found = None
            for user in users_list:
                user_email = user.email if hasattr(user, "email") else user.get("email")
                if user_email == identifier:
                    user_found = user
                    break

            if not user_found:
                console.print(f"[red]❌ User {identifier} not found[/red]")
                return False

            user_id = user_found.id if hasattr(user_found, "id") else user_found.get("id")
        else:
            # Search by username in user_profiles
            profile_response = (
                supabase.table("user_profiles")
                .select("id, username, display_name, role")
                .eq("username", identifier)
                .execute()
            )

            if not profile_response.data:
                console.print(f"[red]❌ User with username '{identifier}' not found[/red]")
                return False

            user_id = profile_response.data[0]["id"]

        # Get team info to verify it exists
        team_response = supabase.table("teams").select("id, name, city").eq("id", team_id).execute()

        if not team_response.data:
            console.print(f"[red]❌ Team ID {team_id} not found[/red]")
            console.print("[yellow]💡 Hint: Use 'manage_users.py teams' to list all teams[/yellow]")
            return False

        team_info = team_response.data[0]
        console.print(f"[green]✓ Found team: {team_info['name']} (ID: {team_info['id']})[/green]")

        # Get current user info
        profile_response = (
            supabase.table("user_profiles").select("username, display_name, role, team_id").eq("id", user_id).execute()
        )
        current_profile = profile_response.data[0] if profile_response.data else {}

        # Update team_id in user_profiles
        update_response = supabase.table("user_profiles").update({"team_id": team_id}).eq("id", user_id).execute()

        if update_response.data:
            console.print("\n[bold green]✅ Team assignment updated successfully![/bold green]")
            console.print(
                f"  User: [cyan]{current_profile.get('username') or current_profile.get('display_name', 'N/A')}[/cyan]"
            )
            console.print(f"  Role: [yellow]{current_profile.get('role', 'N/A')}[/yellow]")
            console.print(f"  Previous Team: [dim]{current_profile.get('team_id', 'None')}[/dim]")
            console.print(f"  New Team: [green]{team_info['name']} [ID: {team_id}][/green]")
            return True
        else:
            console.print("[red]❌ Team assignment failed[/red]")
            return False

    except Exception as e:
        console.print(f"[red]❌ Error updating team: {e}[/red]")
        return False


def list_teams(supabase):
    """List all teams in the system."""
    try:
        console.print("[cyan]📋 Fetching all teams...[/cyan]\n")

        # Get all teams (basic info only due to schema)
        teams_response = supabase.table("teams").select("id, name, city, academy_team").order("name").execute()

        if not teams_response.data:
            console.print("[yellow]No teams found[/yellow]")
            return True

        console.print(f"[bold cyan]🏆 Found {len(teams_response.data)} teams:[/bold cyan]\n")

        # Create a rich table
        table = Table(
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
            box=box.ROUNDED,
            row_styles=["", "dim"],
        )
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Team Name", style="green")
        table.add_column("City", style="blue")
        table.add_column("Type", style="dim")

        for team in teams_response.data:
            team_id = str(team["id"])
            team_name = team["name"]
            city = team.get("city", "N/A")

            # Team type
            team_type = "Academy" if team.get("academy_team") else "Regular"

            table.add_row(team_id, team_name, city, team_type)

        console.print(table)
        console.print(
            "\n[dim]💡 Tip: Use 'manage_users.py team --user USERNAME --team-id ID' to assign users to teams[/dim]"
        )
        return True

    except Exception as e:
        console.print(f"[red]❌ Error listing teams: {e}[/red]")
        return False


def get_user_info(supabase, email):
    """Get detailed information about a user."""
    try:
        # Find user by email
        response = supabase.auth.admin.list_users()
        users_list = response if isinstance(response, list) else getattr(response, "data", {}).get("users", [])

        user_found = None
        for user in users_list:
            user_email = user.email if hasattr(user, "email") else user.get("email")
            if user_email == email:
                user_found = user
                break

        if not user_found:
            return False

        user_id = user_found.id if hasattr(user_found, "id") else user_found.get("id")
        user_found.created_at if hasattr(user_found, "created_at") else user_found.get("created_at")

        # Get profile info
        profile_result = supabase.table("user_profiles").select("*").eq("id", user_id).execute()

        if profile_result.data:
            profile_result.data[0]
        else:
            pass

        return True

    except Exception:
        return False


@app.command("list")
def list_command():
    """List all users in the system."""
    console.print("[bold cyan]🔐 User Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = list_users(supabase)
    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


@app.command("password")
def password_command(
    email: str = typer.Option(..., "--email", "-e", help="User email"),
    password: str | None = typer.Option(None, "--password", "-p", help="New password (if not provided, will prompt)"),
    generate: bool = typer.Option(False, "--generate", "-g", help="Generate secure password"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompts"),
):
    """Change a user's password."""
    console.print("[bold cyan]🔐 User Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    if not confirm and not Confirm.ask(f"⚠️  Change password for {email}?"):
        console.print("[yellow]❌ Password change cancelled[/yellow]")
        raise typer.Exit(0)

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = change_password(supabase, email, password, generate)
    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


@app.command("create")
def create_command(
    email: str = typer.Option(..., "--email", "-e", help="User email"),
    password: str | None = typer.Option(None, "--password", "-p", help="New password (if not provided, will prompt)"),
    role: str = typer.Option(
        "team_fan",
        "--role",
        "-r",
        help="User role (admin, club_manager, club_fan, team_manager, team_player, team_fan)",
    ),
    display_name: str | None = typer.Option(None, "--display-name", "-n", help="Display name for new users"),
    club_id: int | None = typer.Option(None, "--club-id", "-c", help="Club ID for club_manager role"),
    generate: bool = typer.Option(False, "--generate", "-g", help="Generate secure password"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompts"),
):
    """Create a new user."""
    console.print("[bold cyan]🔐 User Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    # Validate role before proceeding
    is_valid, error_msg = validate_role(role)
    if not is_valid:
        console.print(f"[red]❌ {error_msg}[/red]")
        raise typer.Exit(1)

    if not confirm and not Confirm.ask(f"⚠️  Create user {email} with role {role}?"):
        console.print("[yellow]❌ User creation cancelled[/yellow]")
        raise typer.Exit(0)

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = create_user(supabase, email, password, role, display_name, generate, club_id)
    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


@app.command("role")
def role_command(
    user: str = typer.Option(..., "--user", "-u", help="Username or email"),
    role: str = typer.Option(
        ...,
        "--role",
        "-r",
        help="New role (admin, club_manager, club_fan, team_manager, team_player, team_fan)",
    ),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompts"),
):
    """Update a user's role (accepts username or email)."""
    console.print("[bold cyan]🔐 User Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    # Validate role before proceeding
    is_valid, error_msg = validate_role(role)
    if not is_valid:
        console.print(f"[red]❌ {error_msg}[/red]")
        raise typer.Exit(1)

    if not confirm and not Confirm.ask(f"⚠️  Change role for {user} to {role}?"):
        console.print("[yellow]❌ Role change cancelled[/yellow]")
        raise typer.Exit(0)

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = update_user_role(supabase, user, role)
    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


@app.command("info")
def info_command(email: str = typer.Option(..., "--email", "-e", help="User email")):
    """Get detailed information about a user."""
    console.print("[bold cyan]🔐 User Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = get_user_info(supabase, email)
    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


def delete_user(supabase, user_id, skip_confirm=False):
    """Delete a user by ID."""
    try:
        console.print(f"[cyan]🔍 Fetching user: {user_id}...[/cyan]\n")

        # Get profile first to show what we're deleting
        profile_response = supabase.table("user_profiles").select("*, teams(name, city)").eq("id", user_id).execute()

        if not profile_response.data:
            console.print(f"[yellow]⚠️  No profile found for user: {user_id}[/yellow]")
            console.print("[yellow]⚠️  Checking if user exists in auth.users...[/yellow]")
        else:
            profile = profile_response.data[0]
            console.print("[red bold]User to DELETE:[/red bold]")
            console.print(f"  User ID: [cyan]{user_id}[/cyan]")
            console.print(f"  Username: [yellow]{profile.get('username', 'N/A')}[/yellow]")
            console.print(f"  Display Name: {profile.get('display_name', 'N/A')}")
            console.print(f"  Role: [magenta]{profile.get('role', 'N/A')}[/magenta]")
            console.print(f"  Team: {profile.get('teams', {}).get('name', 'N/A') if profile.get('teams') else 'N/A'}")
            console.print()

        # Confirm deletion
        if not skip_confirm:
            if not Confirm.ask(
                "[bold red]⚠️  Are you ABSOLUTELY SURE you want to DELETE this user permanently?[/bold red]"
            ):
                console.print("[yellow]Deletion cancelled[/yellow]")
                return False

        # Delete from user_profiles
        console.print("[cyan]1. Deleting from user_profiles...[/cyan]")
        supabase.table("user_profiles").delete().eq("id", user_id).execute()
        console.print("[green]   ✓ Deleted from user_profiles[/green]")

        # Delete from auth.users
        console.print("[cyan]2. Deleting from auth.users...[/cyan]")
        supabase.auth.admin.delete_user(user_id)
        console.print("[green]   ✓ Deleted from auth.users[/green]")

        console.print(f"\n[bold green]✅ User {user_id} deleted successfully![/bold green]")
        return True

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return False


@app.command("delete")
def delete_command(
    user_id: str = typer.Option(..., "--id", "-i", help="User ID to delete"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompts"),
):
    """Delete a user by ID from both auth.users and user_profiles."""
    console.print("[bold red]🗑️  User Deletion Tool[/bold red]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = delete_user(supabase, user_id, skip_confirm=confirm)
    if success:
        console.print("\n[green]🎉 Deletion completed successfully![/green]")
    else:
        console.print("\n[red]💥 Deletion failed![/red]")
        raise typer.Exit(1)


@app.command("team")
def team_command(
    user: str = typer.Option(..., "--user", "-u", help="User email or username"),
    team_id: int = typer.Option(..., "--team-id", "-t", help="Team ID to assign"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompts"),
):
    """Assign a user to a team."""
    console.print("[bold cyan]👥 User Team Assignment Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    if not confirm and not Confirm.ask(f"⚠️  Assign {user} to team ID {team_id}?"):
        console.print("[yellow]❌ Team assignment cancelled[/yellow]")
        raise typer.Exit(0)

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = update_user_team(supabase, user, team_id)
    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


@app.command("teams")
def teams_command():
    """List all teams in the system."""
    console.print("[bold cyan]🏆 Team Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = list_teams(supabase)
    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


def add_to_roster(
    supabase,
    user_identifier,
    team_id,
    season_id,
    jersey_number,
    first_name=None,
    last_name=None,
    positions=None,
):
    """Add a user to a team roster."""
    try:
        console.print(f"[cyan]🔍 Looking up user: {user_identifier}[/cyan]")

        # Try to find user by UUID, username, or email
        user_id = None
        profile_data = None

        # Check if it's a UUID format
        if len(user_identifier) == 36 and user_identifier.count("-") == 4:
            # Looks like a UUID - check if user exists
            profile_response = (
                supabase.table("user_profiles")
                .select("id, username, first_name, last_name, display_name")
                .eq("id", user_identifier)
                .execute()
            )
            if profile_response.data:
                user_id = user_identifier
                profile_data = profile_response.data[0]
        else:
            # Try by username or email
            found_id, found_identifier, id_type = find_user_by_identifier(supabase, user_identifier)
            if found_id:
                user_id = found_id
                profile_response = (
                    supabase.table("user_profiles")
                    .select("id, username, first_name, last_name, display_name")
                    .eq("id", user_id)
                    .execute()
                )
                if profile_response.data:
                    profile_data = profile_response.data[0]

        if not user_id:
            console.print(f"[red]❌ User '{user_identifier}' not found[/red]")
            return False

        console.print(
            f"[green]✓ Found user: {profile_data.get('username') or profile_data.get('display_name', user_id[:8])}[/green]"
        )

        # Verify team exists
        team_response = supabase.table("teams").select("id, name").eq("id", team_id).execute()
        if not team_response.data:
            console.print(f"[red]❌ Team ID {team_id} not found[/red]")
            return False
        team_name = team_response.data[0]["name"]
        console.print(f"[green]✓ Found team: {team_name}[/green]")

        # Verify season exists
        season_response = supabase.table("seasons").select("id, name").eq("id", season_id).execute()
        if not season_response.data:
            console.print(f"[red]❌ Season ID {season_id} not found[/red]")
            return False
        season_name = season_response.data[0]["name"]
        console.print(f"[green]✓ Found season: {season_name}[/green]")

        # Check if player already exists on this roster
        existing = (
            supabase.table("players")
            .select("id, jersey_number")
            .eq("team_id", team_id)
            .eq("season_id", season_id)
            .eq("user_profile_id", user_id)
            .execute()
        )
        if existing.data:
            console.print(
                f"[yellow]⚠️  User already on roster with jersey #{existing.data[0]['jersey_number']}[/yellow]"
            )
            return False

        # Check if jersey number is taken
        jersey_check = (
            supabase.table("players")
            .select("id, first_name, last_name")
            .eq("team_id", team_id)
            .eq("season_id", season_id)
            .eq("jersey_number", jersey_number)
            .execute()
        )
        if jersey_check.data:
            existing_player = jersey_check.data[0]
            console.print(
                f"[red]❌ Jersey #{jersey_number} already taken by {existing_player.get('first_name', '')} {existing_player.get('last_name', '')}[/red]"
            )
            return False

        # Use profile names if not provided
        if not first_name:
            first_name = (
                profile_data.get("first_name") or profile_data.get("display_name", "").split()[0]
                if profile_data.get("display_name")
                else None
            )
        if not last_name:
            last_name = profile_data.get("last_name") or (
                profile_data.get("display_name", "").split()[-1]
                if profile_data.get("display_name") and len(profile_data.get("display_name", "").split()) > 1
                else None
            )

        # Create roster entry
        player_data = {
            "team_id": team_id,
            "season_id": season_id,
            "jersey_number": jersey_number,
            "user_profile_id": user_id,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
        }

        if positions:
            player_data["positions"] = positions

        insert_response = supabase.table("players").insert(player_data).execute()

        if insert_response.data:
            player_id = insert_response.data[0]["id"]
            console.print("\n[bold green]✅ Added to roster successfully![/bold green]")
            console.print(f"  Player ID: [cyan]{player_id}[/cyan]")
            console.print(f"  Name: [yellow]{first_name or 'N/A'} {last_name or 'N/A'}[/yellow]")
            console.print(f"  Jersey: [bold]#{jersey_number}[/bold]")
            console.print(f"  Team: [green]{team_name}[/green]")
            console.print(f"  Season: [blue]{season_name}[/blue]")
            console.print(f"  Linked User: [dim]{user_id[:8]}...[/dim]")
            return True
        else:
            console.print("[red]❌ Failed to add to roster[/red]")
            return False

    except Exception as e:
        console.print(f"[red]❌ Error adding to roster: {e}[/red]")
        return False


def list_roster(supabase, team_id, season_id=None):
    """List roster for a team."""
    try:
        # Get team info
        team_response = supabase.table("teams").select("id, name").eq("id", team_id).execute()
        if not team_response.data:
            console.print(f"[red]❌ Team ID {team_id} not found[/red]")
            return False
        team_name = team_response.data[0]["name"]

        # Build query
        query = (
            supabase.table("players")
            .select("id, jersey_number, first_name, last_name, user_profile_id, positions, is_active, seasons(name)")
            .eq("team_id", team_id)
        )

        if season_id:
            query = query.eq("season_id", season_id)

        query = query.order("jersey_number")
        roster_response = query.execute()

        if not roster_response.data:
            console.print(f"[yellow]No players found for {team_name}[/yellow]")
            return True

        console.print(f"\n[bold cyan]🏆 Roster for {team_name}[/bold cyan]")
        if season_id:
            season_response = supabase.table("seasons").select("name").eq("id", season_id).execute()
            if season_response.data:
                console.print(f"[dim]Season: {season_response.data[0]['name']}[/dim]")

        console.print(f"[dim]Total players: {len(roster_response.data)}[/dim]\n")

        table = Table(
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
            box=box.ROUNDED,
        )
        table.add_column("#", style="bold cyan", no_wrap=True, width=4)
        table.add_column("Name", style="green", width=25)
        table.add_column("Season", style="blue", width=12)
        table.add_column("Positions", style="yellow", width=15)
        table.add_column("Linked User", style="dim", width=10)
        table.add_column("Active", style="cyan", width=6)

        for player in roster_response.data:
            jersey = str(player["jersey_number"])
            name = f"{player.get('first_name', '') or ''} {player.get('last_name', '') or ''}".strip() or "N/A"
            season = player.get("seasons", {}).get("name", "N/A") if player.get("seasons") else "N/A"
            positions = ", ".join(player.get("positions", [])) if player.get("positions") else "N/A"
            linked = player["user_profile_id"][:8] + "..." if player.get("user_profile_id") else "[dim]None[/dim]"
            active = "[green]✓[/green]" if player.get("is_active") else "[red]✗[/red]"

            table.add_row(jersey, name, season, positions, linked, active)

        console.print(table)
        return True

    except Exception as e:
        console.print(f"[red]❌ Error listing roster: {e}[/red]")
        return False


def remove_from_roster(supabase, player_id):
    """Remove a player from roster (or deactivate)."""
    try:
        # Get player info
        player_response = (
            supabase.table("players").select("*, teams(name), seasons(name)").eq("id", player_id).execute()
        )

        if not player_response.data:
            console.print(f"[red]❌ Player ID {player_id} not found[/red]")
            return False

        player = player_response.data[0]
        console.print("[yellow]⚠️  Player to remove:[/yellow]")
        console.print(f"  #{player['jersey_number']} {player.get('first_name', '')} {player.get('last_name', '')}")
        console.print(f"  Team: {player.get('teams', {}).get('name', 'N/A')}")
        console.print(f"  Season: {player.get('seasons', {}).get('name', 'N/A')}")

        # Deactivate instead of delete to preserve history
        update_response = supabase.table("players").update({"is_active": False}).eq("id", player_id).execute()

        if update_response.data:
            console.print("\n[bold green]✅ Player deactivated from roster[/bold green]")
            return True
        else:
            console.print("[red]❌ Failed to remove from roster[/red]")
            return False

    except Exception as e:
        console.print(f"[red]❌ Error removing from roster: {e}[/red]")
        return False


def list_seasons(supabase):
    """List all seasons."""
    try:
        response = (
            supabase.table("seasons").select("id, name, start_date, end_date").order("start_date", desc=True).execute()
        )

        if not response.data:
            console.print("[yellow]No seasons found[/yellow]")
            return True

        console.print("\n[bold cyan]📅 Available Seasons[/bold cyan]\n")

        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Start", style="blue")
        table.add_column("End", style="blue")

        for season in response.data:
            table.add_row(
                str(season["id"]),
                season["name"],
                str(season.get("start_date", "N/A"))[:10],
                str(season.get("end_date", "N/A"))[:10],
            )

        console.print(table)
        return True

    except Exception as e:
        console.print(f"[red]❌ Error listing seasons: {e}[/red]")
        return False


@app.command("roster")
def roster_command(
    action: str = typer.Argument(..., help="Action: add, list, remove"),
    user: str | None = typer.Option(None, "--user", "-u", help="User UUID, username, or email (for add)"),
    team_id: int | None = typer.Option(None, "--team-id", "-t", help="Team ID"),
    season_id: int | None = typer.Option(None, "--season-id", "-s", help="Season ID (default: current season)"),
    jersey: int | None = typer.Option(None, "--jersey", "-j", help="Jersey number (1-99)"),
    first_name: str | None = typer.Option(
        None, "--first-name", "-f", help="First name (optional, uses profile if not set)"
    ),
    last_name: str | None = typer.Option(
        None, "--last-name", "-l", help="Last name (optional, uses profile if not set)"
    ),
    positions: str | None = typer.Option(None, "--positions", "-p", help="Positions (comma-separated, e.g., 'GK,CB')"),
    player_id: int | None = typer.Option(None, "--player-id", "-i", help="Player ID (for remove)"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompts"),
):
    """Manage team rosters - add users to rosters, list rosters, remove players."""
    console.print("[bold cyan]⚽ Roster Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    action = action.lower()

    if action == "add":
        if not user:
            console.print("[red]❌ --user is required for add action[/red]")
            raise typer.Exit(1)
        if not team_id:
            console.print("[red]❌ --team-id is required for add action[/red]")
            raise typer.Exit(1)
        if not jersey:
            console.print("[red]❌ --jersey is required for add action[/red]")
            raise typer.Exit(1)

        # Default to current season (ID 3 = 2025-2026)
        if not season_id:
            season_id = 3
            console.print(f"[dim]Using current season (ID: {season_id})[/dim]")

        # Parse positions
        pos_list = [p.strip().upper() for p in positions.split(",")] if positions else None

        if not confirm:
            if not Confirm.ask(f"⚠️  Add user to roster (Team {team_id}, Jersey #{jersey})?"):
                console.print("[yellow]❌ Cancelled[/yellow]")
                raise typer.Exit(0)

        success = add_to_roster(supabase, user, team_id, season_id, jersey, first_name, last_name, pos_list)

    elif action == "list":
        if not team_id:
            console.print("[red]❌ --team-id is required for list action[/red]")
            raise typer.Exit(1)
        success = list_roster(supabase, team_id, season_id)

    elif action == "remove":
        if not player_id:
            console.print("[red]❌ --player-id is required for remove action[/red]")
            raise typer.Exit(1)

        if not confirm and not Confirm.ask(f"⚠️  Remove player ID {player_id} from roster?"):
            console.print("[yellow]❌ Cancelled[/yellow]")
            raise typer.Exit(0)

        success = remove_from_roster(supabase, player_id)

    else:
        console.print(f"[red]❌ Unknown action: {action}[/red]")
        console.print("[yellow]Valid actions: add, list, remove[/yellow]")
        raise typer.Exit(1)

    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


@app.command("seasons")
def seasons_command():
    """List all seasons in the system."""
    console.print("[bold cyan]📅 Season Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = list_seasons(supabase)
    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


@app.command("env")
def env_command():
    """Show current environment configuration."""
    console.print("[bold cyan]🌍 Environment Configuration[/bold cyan]\n")

    # Get APP_ENV before loading
    app_env = os.getenv("APP_ENV", "dev")

    # Load environment
    load_environment()

    # Get environment variables
    supabase_url = os.getenv("SUPABASE_URL", "Not set")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "Not set")
    environment_var = os.getenv("ENVIRONMENT", "Not set")

    # Determine environment file
    env_file = f".env.{app_env}"
    env_file_exists = os.path.exists(env_file)

    # Create info table
    table = Table(
        show_header=False,
        box=box.ROUNDED,
        padding=(0, 2),
    )
    table.add_column("Setting", style="cyan bold", no_wrap=True)
    table.add_column("Value", style="white")

    # Environment info
    table.add_row("Current Environment", f"[yellow bold]{app_env}[/yellow bold]")
    table.add_row(
        "Environment File",
        f"{env_file} {'[green]✓ exists[/green]' if env_file_exists else '[red]✗ not found[/red]'}",
    )
    table.add_row("ENVIRONMENT var", environment_var)

    # Supabase info
    if supabase_url.startswith("http://127.0.0.1") or supabase_url.startswith("http://localhost"):
        url_display = f"[blue]{supabase_url}[/blue] [dim](local)[/dim]"
    elif "supabase.co" in supabase_url:
        # Show only domain for cloud
        url_display = f"[green]{supabase_url.split('/')[2]}[/green] [dim](cloud)[/dim]"
    else:
        url_display = supabase_url

    table.add_row("Supabase URL", url_display)

    # Show key status (don't show actual key)
    if supabase_key and supabase_key != "Not set":
        key_preview = f"{supabase_key[:20]}..." if len(supabase_key) > 20 else supabase_key
        table.add_row("Service Key", f"[dim]{key_preview}[/dim] [green]✓ set[/green]")
    else:
        table.add_row("Service Key", "[red]✗ not set[/red]")

    console.print(table)

    # Additional info
    console.print("\n[bold]Available environment files:[/bold]")
    for env_name in ["local", "dev", "prod"]:
        env_path = f".env.{env_name}"
        if os.path.exists(env_path):
            active = " [yellow]← ACTIVE[/yellow]" if env_name == app_env else ""
            console.print(f"  [green]✓[/green] {env_path}{active}")
        else:
            console.print(f"  [dim]✗ {env_path}[/dim]")

    console.print("\n[dim]💡 Tip: Use '../switch-env.sh <env>' to change environments[/dim]")


if __name__ == "__main__":
    app()
