"""
RabbitMQ connection and message publishing.

Uses kombu (the same library Celery uses) for educational consistency.
"""

import json
from typing import Any

from celery import Celery
from kombu import Connection, Exchange, Producer, Queue

from .config import QueueConfig


class RabbitMQClient:
    """RabbitMQ client for publishing messages."""

    def __init__(self, config: QueueConfig):
        """
        Initialize RabbitMQ client.

        Args:
            config: Queue configuration
        """
        self.config = config
        self.connection: Connection | None = None
        self.producer: Producer | None = None

    def connect(self) -> tuple[bool, str]:
        """
        Connect to RabbitMQ broker.

        Returns:
            Tuple of (success, message)
        """
        try:
            self.connection = Connection(self.config.broker_url)
            self.connection.connect()

            # Create producer
            self.producer = Producer(self.connection)

            return True, f"Connected to {self.config.get_sanitized_broker_url()}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def disconnect(self) -> None:
        """Disconnect from RabbitMQ broker."""
        if self.connection:
            self.connection.release()
            self.connection = None
            self.producer = None

    def publish_message(
        self,
        message: dict[str, Any],
        queue_name: str | None = None,
        exchange_name: str | None = None,
        routing_key: str | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Publish a message to RabbitMQ.

        Args:
            message: Message payload
            queue_name: Target queue name (defaults to config)
            exchange_name: Exchange name (defaults to config)
            routing_key: Routing key (defaults to config)

        Returns:
            Tuple of (success, message_id, publish_info)
        """
        if not self.connection or not self.producer:
            return False, "", {"error": "Not connected to RabbitMQ"}

        queue_name = queue_name or self.config.default_queue
        exchange_name = exchange_name or self.config.default_exchange
        routing_key = routing_key or self.config.default_routing_key

        try:
            # Create exchange
            exchange = Exchange(exchange_name, type="topic", durable=True)

            # Create queue
            queue = Queue(queue_name, exchange=exchange, routing_key=routing_key)

            # Bind queue (ensure it exists)
            queue.maybe_bind(self.connection)
            queue.declare()

            # Publish message
            self.producer.publish(
                message,
                exchange=exchange,
                routing_key=routing_key,
                serializer="json",
                content_type="application/json",
                declare=[queue],  # Ensure queue is declared before publishing
            )

            # Get queue stats
            with self.connection.channel() as channel:
                queue_info = queue.queue_declare(passive=True, channel=channel)
                message_count = queue_info.message_count
                consumer_count = queue_info.consumer_count

            publish_info = {
                "queue": queue_name,
                "exchange": exchange_name,
                "routing_key": routing_key,
                "message_count": message_count,
                "consumer_count": consumer_count,
                "serializer": "json",
                "content_type": "application/json",
            }

            return True, "Message published successfully", publish_info

        except Exception as e:
            return False, f"Publish failed: {e}", {}

    def get_queue_stats(
        self, queue_name: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Get queue statistics.

        Args:
            queue_name: Queue name (defaults to config)

        Returns:
            Tuple of (success, stats_dict)
        """
        if not self.connection:
            return False, {"error": "Not connected to RabbitMQ"}

        queue_name = queue_name or self.config.default_queue

        try:
            exchange = Exchange(self.config.default_exchange, type="topic", durable=True)
            queue = Queue(
                queue_name, exchange=exchange, routing_key=self.config.default_routing_key
            )

            with self.connection.channel() as channel:
                info = queue.queue_declare(passive=True, channel=channel)

                stats = {
                    "queue_name": queue_name,
                    "message_count": info.message_count,
                    "consumer_count": info.consumer_count,
                }

                return True, stats

        except Exception as e:
            return False, {"error": f"Failed to get queue stats: {e}"}

    def __enter__(self) -> "RabbitMQClient":
        """Context manager entry."""
        success, message = self.connect()
        if not success:
            raise ConnectionError(message)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()


class CeleryClient:
    """Celery client for submitting tasks directly."""

    def __init__(self, config: QueueConfig):
        """
        Initialize Celery client.

        Args:
            config: Queue configuration
        """
        self.config = config
        self.app = Celery(
            "queue_cli", broker=config.broker_url, backend=config.result_backend
        )
        self.app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
        )

    def send_task(
        self, task_name: str, args: tuple = (), kwargs: dict | None = None
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Send a task to Celery.

        Args:
            task_name: Full task name (e.g., 'celery_tasks.match_tasks.process_match_data')
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Tuple of (success, task_id, task_info)
        """
        try:
            task = self.app.send_task(task_name, args=args, kwargs=kwargs or {})

            task_info = {
                "task_id": task.id,
                "task_name": task_name,
                "state": task.state,
            }

            return True, task.id, task_info

        except Exception as e:
            return False, "", {"error": f"Failed to send task: {e}"}

    def get_task_result(self, task_id: str, timeout: float = 1.0) -> dict[str, Any]:
        """
        Get task result.

        Args:
            task_id: Task ID
            timeout: Timeout in seconds

        Returns:
            Task result info
        """
        try:
            result = self.app.AsyncResult(task_id)

            info = {
                "task_id": task_id,
                "state": result.state,
                "ready": result.ready(),
                "successful": result.successful() if result.ready() else None,
            }

            if result.ready():
                if result.successful():
                    info["result"] = result.result
                else:
                    info["error"] = str(result.info)

            return info

        except Exception as e:
            return {"task_id": task_id, "error": f"Failed to get result: {e}"}
