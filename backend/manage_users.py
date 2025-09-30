#!/usr/bin/env python3
"""
Comprehensive user management script for Supabase environments.
Supports password changes, user creation, role management, and user info.
"""

import os
import sys
import secrets
import string
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table
from supabase import create_client

app = typer.Typer()
console = Console()

def load_environment():
    """Load environment variables based on APP_ENV or default to dev."""
    load_dotenv()
    app_env = os.getenv('APP_ENV', 'dev')
    env_file = f".env.{app_env}"
    if os.path.exists(env_file):
        print(f"Loading environment: {app_env} from {env_file}")
        load_dotenv(env_file, override=True)
    else:
        print(f"Environment file {env_file} not found, using defaults")

def generate_secure_password(length=12):
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def get_supabase_client():
    """Create Supabase client with service key."""
    supabase_url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')

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
        users_list = response if isinstance(response, list) else getattr(response, 'data', {}).get('users', [])

        if not users_list:
            console.print("[yellow]No users found[/yellow]")
            return True

        console.print(f"\n[bold cyan]👥 Found {len(users_list)} users:[/bold cyan]")

        # Create a rich table for better display
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Email", style="cyan")
        table.add_column("ID", style="dim", width=36)  # Full UUID width
        table.add_column("Role", style="green")
        table.add_column("Display Name", style="yellow")
        table.add_column("Team ID", style="blue")
        table.add_column("Created", style="dim")

        for user in users_list:
            user_id = user.id if hasattr(user, 'id') else user.get('id')
            email = user.email if hasattr(user, 'email') else user.get('email')
            created_at = user.created_at if hasattr(user, 'created_at') else user.get('created_at')

            # Get profile info
            try:
                profile_result = supabase.table('user_profiles').select('role, display_name, team_id').eq('id', user_id).execute()
                if profile_result.data:
                    profile = profile_result.data[0]
                    role = profile.get('role', 'No role')
                    display_name = profile.get('display_name', 'No display name')
                    team_id = profile.get('team_id', 'No team')
                else:
                    role = display_name = team_id = "No profile"
            except:
                role = display_name = team_id = "Profile error"

            table.add_row(
                email,
                user_id,  # Show full ID now that we have width set
                role,
                display_name,
                str(team_id),
                str(created_at)[:10] if created_at else "Unknown"  # Show just date
            )

        console.print(table)
        return True

    except Exception as e:
        console.print(f"[red]❌ Error listing users: {e}[/red]")
        return False

def change_password(supabase, email, new_password=None, generate=False):
    """Change a user's password."""
    try:
        print(f"🔍 Looking up user: {email}")

        # Find user by email
        response = supabase.auth.admin.list_users()
        users_list = response if isinstance(response, list) else getattr(response, 'data', {}).get('users', [])

        user_found = None
        for user in users_list:
            user_email = user.email if hasattr(user, 'email') else user.get('email')
            if user_email == email:
                user_found = user
                break

        if not user_found:
            print(f"❌ User {email} not found")
            return False

        user_id = user_found.id if hasattr(user_found, 'id') else user_found.get('id')
        print(f"✅ Found user: {user_id}")

        # Handle password
        if generate:
            new_password = generate_secure_password()
            print(f"🔐 Generated secure password: {new_password}")
        elif not new_password:
            new_password = Prompt.ask("Enter new password", password=True)
            if not new_password:
                console.print("[red]❌ Password cannot be empty[/red]")
                return False

        # Reset password using admin API
        print(f"🔄 Changing password for {email}...")

        reset_response = supabase.auth.admin.update_user_by_id(
            user_id,
            {"password": new_password}
        )

        if reset_response.user:
            print(f"✅ Password changed successfully for {email}")
            if generate:
                print(f"🔑 New password: {new_password}")
            return True
        else:
            print(f"❌ Password change failed")
            return False

    except Exception as e:
        print(f"❌ Error changing password: {e}")
        return False

def create_user(supabase, email, password=None, role='user', display_name=None, generate=False):
    """Create a new user."""
    try:
        # Handle password
        if generate:
            password = generate_secure_password()
            print(f"🔐 Generated secure password: {password}")
        elif not password:
            password = Prompt.ask("Enter password for new user", password=True)
            if not password:
                console.print("[red]❌ Password cannot be empty[/red]")
                return False

        if not display_name:
            display_name = email.split('@')[0]

        print(f"👤 Creating user: {email}")

        # Create user using admin API
        create_response = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True  # Auto-confirm email
        })

        if create_response.user:
            user_id = create_response.user.id
            print(f"✅ User created successfully: {user_id}")

            # Create user profile
            profile_data = {
                "id": user_id,
                "role": role,
                "display_name": display_name
            }

            profile_response = supabase.table('user_profiles').insert(profile_data).execute()

            if profile_response.data:
                print(f"✅ User profile created with role: {role}")
            else:
                print(f"⚠️ User created but profile creation failed")

            if generate:
                print(f"🔑 Password: {password}")

            print(f"📧 Email: {email}")
            print(f"👤 Role: {role}")
            print(f"📝 Display Name: {display_name}")

            return True
        else:
            print(f"❌ User creation failed")
            return False

    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return False

def update_user_role(supabase, email, new_role):
    """Update a user's role."""
    try:
        print(f"🔍 Looking up user: {email}")

        # Find user by email
        response = supabase.auth.admin.list_users()
        users_list = response if isinstance(response, list) else getattr(response, 'data', {}).get('users', [])

        user_found = None
        for user in users_list:
            user_email = user.email if hasattr(user, 'email') else user.get('email')
            if user_email == email:
                user_found = user
                break

        if not user_found:
            print(f"❌ User {email} not found")
            return False

        user_id = user_found.id if hasattr(user_found, 'id') else user_found.get('id')

        # Update role in user_profiles
        update_response = supabase.table('user_profiles').update({
            'role': new_role
        }).eq('id', user_id).execute()

        if update_response.data:
            print(f"✅ Role updated successfully for {email}")
            print(f"👤 New role: {new_role}")
            return True
        else:
            print(f"❌ Role update failed")
            return False

    except Exception as e:
        print(f"❌ Error updating role: {e}")
        return False

def get_user_info(supabase, email):
    """Get detailed information about a user."""
    try:
        print(f"🔍 Looking up user: {email}")

        # Find user by email
        response = supabase.auth.admin.list_users()
        users_list = response if isinstance(response, list) else getattr(response, 'data', {}).get('users', [])

        user_found = None
        for user in users_list:
            user_email = user.email if hasattr(user, 'email') else user.get('email')
            if user_email == email:
                user_found = user
                break

        if not user_found:
            print(f"❌ User {email} not found")
            return False

        user_id = user_found.id if hasattr(user_found, 'id') else user_found.get('id')
        created_at = user_found.created_at if hasattr(user_found, 'created_at') else user_found.get('created_at')

        # Get profile info
        profile_result = supabase.table('user_profiles').select('*').eq('id', user_id).execute()

        print(f"\n👤 User Information for {email}")
        print("=" * 60)
        print(f"🆔 User ID: {user_id}")
        print(f"📧 Email: {email}")
        print(f"📅 Created: {created_at}")

        if profile_result.data:
            profile = profile_result.data[0]
            print(f"👤 Role: {profile.get('role', 'No role')}")
            print(f"📝 Display Name: {profile.get('display_name', 'No display name')}")
            print(f"🏆 Team ID: {profile.get('team_id', 'No team')}")
            print(f"🔢 Player Number: {profile.get('player_number', 'No number')}")
            print(f"📍 Positions: {profile.get('positions', 'No positions')}")
            print(f"📅 Profile Created: {profile.get('created_at', 'Unknown')}")
            print(f"📅 Profile Updated: {profile.get('updated_at', 'Unknown')}")
        else:
            print("❌ No profile found")

        return True

    except Exception as e:
        print(f"❌ Error getting user info: {e}")
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
    password: Optional[str] = typer.Option(None, "--password", "-p", help="New password (if not provided, will prompt)"),
    generate: bool = typer.Option(False, "--generate", "-g", help="Generate secure password"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompts")
):
    """Change a user's password."""
    console.print("[bold cyan]🔐 User Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    if not confirm:
        if not Confirm.ask(f"⚠️  Change password for {email}?"):
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
    password: Optional[str] = typer.Option(None, "--password", "-p", help="New password (if not provided, will prompt)"),
    role: str = typer.Option("user", "--role", "-r", help="User role"),
    display_name: Optional[str] = typer.Option(None, "--display-name", "-n", help="Display name for new users"),
    generate: bool = typer.Option(False, "--generate", "-g", help="Generate secure password"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompts")
):
    """Create a new user."""
    console.print("[bold cyan]🔐 User Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    if not confirm:
        if not Confirm.ask(f"⚠️  Create user {email} with role {role}?"):
            console.print("[yellow]❌ User creation cancelled[/yellow]")
            raise typer.Exit(0)

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = create_user(supabase, email, password, role, display_name, generate)
    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


@app.command("role")
def role_command(
    email: str = typer.Option(..., "--email", "-e", help="User email"),
    role: str = typer.Option(..., "--role", "-r", help="New role"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompts")
):
    """Update a user's role."""
    console.print("[bold cyan]🔐 User Management Tool[/bold cyan]")
    console.print(f"🌍 Environment: [yellow]{os.getenv('APP_ENV', 'dev')}[/yellow]\n")

    if not confirm:
        if not Confirm.ask(f"⚠️  Change role for {email} to {role}?"):
            console.print("[yellow]❌ Role change cancelled[/yellow]")
            raise typer.Exit(0)

    load_environment()
    supabase = get_supabase_client()

    if not supabase:
        raise typer.Exit(1)

    success = update_user_role(supabase, email, role)
    if success:
        console.print("\n[green]🎉 Operation completed successfully![/green]")
    else:
        console.print("\n[red]💥 Operation failed![/red]")
        raise typer.Exit(1)


@app.command("info")
def info_command(
    email: str = typer.Option(..., "--email", "-e", help="User email")
):
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


if __name__ == "__main__":
    app()