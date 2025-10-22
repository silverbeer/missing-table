"""
Send command - publishes messages to RabbitMQ queue.
"""

import json
from pathlib import Path
from typing import Any, Optional

import typer

from ..core.config import QueueConfig
from ..core.rabbitmq import CeleryClient, RabbitMQClient
from ..core.schema import SchemaValidator
from ..core.templates import TemplateManager
from ..utils.display import (
    console,
    print_connection_info,
    print_debug_mode,
    print_divider,
    print_error,
    print_header,
    print_info,
    print_json,
    print_next_steps,
    print_publish_info,
    print_success,
    print_task_info,
    print_validation_result,
)


def send_message(
    template: Optional[str] = typer.Option(
        None, "--template", "-t", help="Template name to use"
    ),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="JSON file to send"),
    json_str: Optional[str] = typer.Option(
        None, "--json", "-j", help="JSON string to send"
    ),
    queue: Optional[str] = typer.Option(
        None, "--queue", "-q", help="Target queue name"
    ),
    use_celery: bool = typer.Option(
        True, "--celery/--rabbitmq", help="Use Celery task vs direct RabbitMQ publish"
    ),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),
) -> None:
    """
    Send a message to the queue.

    Examples:
        # Send using a template
        uv run python queue_cli.py send --template completed-match

        # Send from a file
        uv run python queue_cli.py send --file my-match.json

        # Send JSON string
        uv run python queue_cli.py send --json '{"home_team": "..."}'

        # Use direct RabbitMQ publish (for learning)
        uv run python queue_cli.py send --template tbd-match --rabbitmq

        # Enable debug mode
        uv run python queue_cli.py send --template minimal --debug
    """
    print_header("Sending Message to Queue")

    if debug:
        print_debug_mode()

    # Load configuration
    config = QueueConfig.from_env()

    if debug:
        print_divider()
        print_info(f"Broker: {config.get_sanitized_broker_url()}")
        print_info(f"Result Backend: {config.get_sanitized_result_backend()}")
        print_info(f"Default Queue: {config.default_queue}")
        print_divider()

    # Load message data
    message_data = _load_message_data(template, file, json_str)
    if not message_data:
        console.print(
            "[red]❌ Error: Must provide --template, --file, or --json[/red]"
        )
        raise typer.Exit(1)

    # Validate message
    validator = SchemaValidator()
    is_valid, errors, warnings = validator.validate(message_data)

    print_validation_result(is_valid, errors, warnings)

    if not is_valid:
        console.print("\n[red]❌ Message validation failed. Cannot send.[/red]")
        raise typer.Exit(1)

    # Translate to internal schema
    internal_data = validator.translate_to_internal(message_data)

    if debug:
        print_json(internal_data, "Internal Message Format")

    # Send message
    queue_name = queue or config.default_queue

    if use_celery:
        _send_via_celery(config, internal_data, debug)
    else:
        _send_via_rabbitmq(config, internal_data, queue_name, debug)

    # Print next steps
    if use_celery:
        # Task ID will be printed in _send_via_celery
        pass
    else:
        print_next_steps("N/A", queue_name)


def _load_message_data(
    template: Optional[str], file: Optional[Path], json_str: Optional[str]
) -> dict[str, Any] | None:
    """Load message data from various sources."""
    if template:
        template_mgr = TemplateManager()
        data = template_mgr.load_template(template)
        if not data:
            console.print(f"[red]❌ Template not found: {template}[/red]")
            raise typer.Exit(1)
        return data

    if file:
        if not file.exists():
            console.print(f"[red]❌ File not found: {file}[/red]")
            raise typer.Exit(1)

        with open(file) as f:
            return json.load(f)

    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ Invalid JSON: {e}[/red]")
            raise typer.Exit(1)

    return None


def _send_via_celery(
    config: QueueConfig, message_data: dict[str, Any], debug: bool
) -> None:
    """Send message via Celery task."""
    print_connection_info(config.get_sanitized_broker_url(), True)

    celery_client = CeleryClient(config)

    task_name = "celery_tasks.match_tasks.process_match_data"

    if debug:
        print_info(f"Task Name: {task_name}")
        print_info("Submitting task...")

    success, task_id, task_info = celery_client.send_task(
        task_name, kwargs={"match_data": message_data}
    )

    if success:
        print_success("Task submitted successfully!")
        print_task_info(task_id, task_name, task_info.get("state", "PENDING"))
        print_next_steps(task_id, config.default_queue)
    else:
        error = task_info.get("error", "Unknown error")
        print_error(f"Failed to submit task: {error}")
        raise typer.Exit(1)


def _send_via_rabbitmq(
    config: QueueConfig, message_data: dict[str, Any], queue_name: str, debug: bool
) -> None:
    """Send message via direct RabbitMQ publish."""
    print_connection_info(config.get_sanitized_broker_url(), False)

    try:
        with RabbitMQClient(config) as client:
            print_connection_info(config.get_sanitized_broker_url(), True)

            if debug:
                print_info(f"Publishing to queue: {queue_name}")
                print_info(f"Exchange: {config.default_exchange}")
                print_info(f"Routing Key: {config.default_routing_key}")

            success, message, publish_info = client.publish_message(
                message_data, queue_name=queue_name
            )

            if success:
                print_success(message)
                print_publish_info(
                    queue=publish_info["queue"],
                    exchange=publish_info["exchange"],
                    routing_key=publish_info["routing_key"],
                    message_count=publish_info["message_count"],
                    consumer_count=publish_info["consumer_count"],
                )
            else:
                print_error(f"Failed to publish: {message}")
                raise typer.Exit(1)

    except Exception as e:
        print_error(f"Connection error: {e}")
        raise typer.Exit(1)
