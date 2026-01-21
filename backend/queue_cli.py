#!/usr/bin/env python3
"""
Queue CLI - Interactive tool for testing RabbitMQ/Celery queues.

A comprehensive CLI tool for:
- Sending messages to RabbitMQ queues
- Managing message templates
- Monitoring task execution
- Learning about distributed messaging systems

Examples:
    # Send a message using a template
    uv run python queue_cli.py send --template completed-match

    # List available templates
    uv run python queue_cli.py templates

    # Show specific template
    uv run python queue_cli.py templates --show tbd-match

    # Send with debug output
    uv run python queue_cli.py send --template minimal --debug

    # Use direct RabbitMQ (instead of Celery)
    uv run python queue_cli.py send --template scheduled-match --rabbitmq
"""

import typer
from rich.console import Console

from queue_cli.commands.send import send_message
from queue_cli.commands.templates import templates_command

# Create Typer app
app = typer.Typer(
    name="queue-cli",
    help="Interactive CLI tool for testing RabbitMQ/Celery queues",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()


@app.command("send")
def send(
    template: str = typer.Option(None, "--template", "-t", help="Template name to use"),
    file: str = typer.Option(None, "--file", "-f", help="JSON file to send"),
    json_str: str = typer.Option(None, "--json", "-j", help="JSON string to send"),
    queue: str = typer.Option(None, "--queue", "-q", help="Target queue name"),
    use_celery: bool = typer.Option(True, "--celery/--rabbitmq", help="Use Celery task vs direct RabbitMQ publish"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),
) -> None:
    """
    Send a message to the queue.

    This is the primary command for testing queue functionality. Messages can be:
    - Loaded from built-in templates (--template)
    - Read from JSON files (--file)
    - Passed directly as JSON (--json)

    By default, messages are sent via Celery tasks (--celery), which is the
    production method. Use --rabbitmq to publish directly to RabbitMQ for
    educational purposes and to see the low-level mechanics.
    """
    from pathlib import Path

    send_message(
        template=template,
        file=Path(file) if file else None,
        json_str=json_str,
        queue=queue,
        use_celery=use_celery,
        debug=debug,
    )


@app.command("templates")
def templates(
    show: str = typer.Option(None, "--show", "-s", help="Show specific template"),
) -> None:
    """
    Manage message templates.

    Templates are pre-configured message payloads for common scenarios:
    - completed-match: Match with final scores
    - scheduled-match: Upcoming match without scores
    - tbd-match: Played match, awaiting scores
    - minimal: Required fields only

    List all templates or show a specific one with --show.
    """
    templates_command(show=show)


@app.callback()
def main() -> None:
    """
    Queue CLI - Interactive tool for testing RabbitMQ/Celery queues.

    This tool helps you learn about distributed messaging systems by:
    1. Sending messages to RabbitMQ queues
    2. Monitoring Celery task execution
    3. Understanding message schemas and validation
    4. Visualizing the message flow

    Phase 1 commands:
    - send: Send messages to the queue
    - templates: Manage message templates

    Coming soon (Phase 2+):
    - status: Check task status
    - queues: View queue statistics
    - workers: Monitor worker activity
    - watch: Real-time queue monitoring
    """
    pass


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print("Queue CLI v0.1.0 - Phase 1")
        raise typer.Exit()


@app.command()
def version(
    version_flag: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version",
    ),
) -> None:
    """Show version information."""
    pass


if __name__ == "__main__":
    app()
