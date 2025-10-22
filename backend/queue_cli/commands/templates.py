"""
Templates command - manage message templates.
"""

from typing import Optional

import typer

from ..core.templates import TemplateManager
from ..utils.display import console, print_header, print_json, print_template_list


def list_templates() -> None:
    """
    List all available templates.

    Examples:
        uv run python queue_cli.py templates
    """
    template_mgr = TemplateManager()
    templates = template_mgr.list_templates()

    print_template_list(templates)


def show_template(name: str) -> None:
    """
    Show a specific template.

    Args:
        name: Template name

    Examples:
        uv run python queue_cli.py templates --show completed-match
    """
    template_mgr = TemplateManager()
    data = template_mgr.load_template(name)

    if not data:
        console.print(f"[red]❌ Template not found: {name}[/red]")
        raise typer.Exit(1)

    print_header(f"Template: {name}")
    print_json(data)


def templates_command(
    show: Optional[str] = typer.Option(
        None, "--show", "-s", help="Show specific template"
    ),
) -> None:
    """
    Manage message templates.

    Examples:
        # List all templates
        uv run python queue_cli.py templates

        # Show specific template
        uv run python queue_cli.py templates --show completed-match
    """
    if show:
        show_template(show)
    else:
        list_templates()
