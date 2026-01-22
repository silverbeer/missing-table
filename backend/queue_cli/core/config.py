"""
Configuration management for queue CLI.

Handles loading configuration from environment variables and config files.
"""

import os
from dataclasses import dataclass


@dataclass
class QueueConfig:
    """Queue CLI configuration."""

    broker_url: str
    result_backend: str
    default_queue: str = "matches"
    default_exchange: str = "matches"
    default_routing_key: str = "matches.process"

    @classmethod
    def from_env(cls, env: str | None = None) -> "QueueConfig":
        """
        Load configuration from environment variables.

        Args:
            env: Environment name (local, dev, prod). Defaults to current environment.

        Returns:
            QueueConfig instance
        """
        # Get broker URL from environment
        broker_url = os.getenv(
            "CELERY_BROKER_URL",
            os.getenv(
                "RABBITMQ_URL",
                "amqp://admin:admin123@localhost:5672//",  # pragma: allowlist secret
            ),
        )

        # Get result backend from environment
        result_backend = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0"))

        return cls(
            broker_url=broker_url,
            result_backend=result_backend,
            default_queue="matches",
            default_exchange="matches",
            default_routing_key="matches.process",
        )

    def get_sanitized_broker_url(self) -> str:
        """Get broker URL with credentials hidden."""
        if "@" in self.broker_url:
            # Split on @ and return everything after it
            return self.broker_url.split("@")[-1]
        return self.broker_url

    def get_sanitized_result_backend(self) -> str:
        """Get result backend URL with credentials hidden."""
        if "@" in self.result_backend:
            return self.result_backend.split("@")[-1]
        return self.result_backend
