"""
Rich display utilities for beautiful CLI output.
"""

import json
from typing import Any

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_header(title: str) -> None:
    """Print a formatted header."""
    console.print()
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    console.print()


def print_section(title: str, emoji: str = "📋") -> None:
    """Print a section header."""
    console.print(f"\n{emoji} [bold]{title}[/bold]")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"  [green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"  [red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"  [yellow]⚠[/yellow] {message}")


def print_info(message: str, bullet: str = "•") -> None:
    """Print an info message."""
    console.print(f"  {bullet} {message}")


def print_json(data: dict[str, Any], title: str | None = None) -> None:
    """Print formatted JSON."""
    if title:
        print_section(title, "📨")

    json_str = json.dumps(data, indent=2)
    console.print(JSON(json_str))


def print_key_value(key: str, value: Any, indent: int = 1) -> None:
    """Print a key-value pair."""
    indent_str = "  " * indent
    console.print(f"{indent_str}[cyan]{key}:[/cyan] {value}")


def print_connection_info(broker_url: str, is_connected: bool = False) -> None:
    """Print connection information."""
    print_section("RabbitMQ Connection", "🔌")

    status = "[green]Established[/green]" if is_connected else "[yellow]Connecting...[/yellow]"

    print_info(f"Broker: {broker_url}")
    print_info(f"Status: {status}")


def print_publish_info(
    queue: str,
    exchange: str,
    routing_key: str,
    message_count: int,
    consumer_count: int,
) -> None:
    """Print message publish information."""
    print_section("Message Published", "📤")

    print_info(f"Queue: [bold]{queue}[/bold]")
    print_info(f"Exchange: {exchange}")
    print_info(f"Routing Key: {routing_key}")
    print_info(f"Messages in Queue: {message_count}")
    print_info(f"Active Consumers: {consumer_count}")


def print_validation_result(is_valid: bool, errors: list[str], warnings: list[str]) -> None:
    """Print validation results."""
    print_section("Message Validation", "📋")

    if is_valid:
        print_success("Schema validation passed")
    else:
        print_error("Schema validation failed")

    for error in errors:
        print_error(error)

    for warning in warnings:
        print_warning(warning)


def print_task_info(task_id: str, task_name: str, state: str) -> None:
    """Print Celery task information."""
    print_section("Celery Task", "⚙️")

    print_info(f"Task ID: [bold]{task_id}[/bold]")
    print_info(f"Task Name: {task_name}")
    print_info(f"State: [bold]{state}[/bold]")


def print_next_steps(task_id: str, queue: str) -> None:
    """Print next steps for the user."""
    console.print()
    console.print("[bold]🔍 Next Steps:[/bold]")
    console.print(f"  • Check task status: [cyan]uv run python queue_cli.py status {task_id}[/cyan]")
    console.print(f"  • View queue: [cyan]uv run python queue_cli.py queues --name {queue}[/cyan]")
    console.print("  • View workers: [cyan]uv run python queue_cli.py workers[/cyan]")
    console.print()


def print_template_list(templates: list[str]) -> None:
    """Print list of available templates."""
    print_header("Available Templates")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Template Name", style="cyan")
    table.add_column("Description")

    template_descriptions = {
        "completed-match": "Match with final scores",
        "scheduled-match": "Upcoming match without scores",
        "tbd-match": "Played match, awaiting scores",
        "minimal": "Required fields only",
    }

    for template in sorted(templates):
        desc = template_descriptions.get(template, "Custom template")
        table.add_row(template, desc)

    console.print(table)
    console.print()


def print_queue_stats(stats: dict[str, Any]) -> None:
    """Print queue statistics."""
    print_header("Queue Statistics")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Queue", style="cyan")
    table.add_column("Messages", justify="right")
    table.add_column("Consumers", justify="right")

    table.add_row(
        stats.get("queue_name", "N/A"),
        str(stats.get("message_count", 0)),
        str(stats.get("consumer_count", 0)),
    )

    console.print(table)
    console.print()


def print_debug_mode() -> None:
    """Print debug mode indicator."""
    console.print("[yellow]🐛 Debug mode enabled[/yellow]")


def print_divider() -> None:
    """Print a visual divider."""
    console.print("[dim]" + "─" * 80 + "[/dim]")
