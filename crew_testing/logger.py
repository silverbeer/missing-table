"""
CrewAI Testing Logger - Centralized logging with rich formatting

Provides structured logging for workflows and agents with:
- File-based logging to crew_testing/logs/
- Console output with rich formatting
- Symlinks to latest logs for easy access
- Automatic log rotation and cleanup
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler

console = Console()


class CrewLogger:
    """Manages logging for CrewAI testing workflows"""

    def __init__(self, name: str, log_type: str = "workflow"):
        """
        Initialize logger

        Args:
            name: Logger name (e.g., "phase2", "architect", "forge")
            log_type: Type of log ("workflow" or "agent")
        """
        self.name = name
        self.log_type = log_type
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Setup log directories
        self.base_dir = Path("crew_testing/logs")
        self.workflow_dir = self.base_dir / "workflows"
        self.agent_dir = self.base_dir / "agents"
        self.latest_dir = self.base_dir / "latest"

        for dir in [self.base_dir, self.workflow_dir, self.agent_dir, self.latest_dir]:
            dir.mkdir(parents=True, exist_ok=True)

        # Determine log file path
        if log_type == "workflow":
            self.log_file = self.workflow_dir / f"{name}_{self.timestamp}.log"
            self.latest_link = self.latest_dir / f"{name}.log"
        else:  # agent
            self.log_file = self.agent_dir / f"{name}_{self.timestamp}.log"
            self.latest_link = self.latest_dir / f"{name}.log"

        # Create logger
        self.logger = logging.getLogger(f"crew.{log_type}.{name}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []  # Clear existing handlers

        # File handler (detailed logs)
        file_handler = logging.FileHandler(self.log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Console handler (rich formatting)
        console_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=True,
            show_time=False,
            show_path=False
        )
        console_handler.setLevel(logging.INFO)
        self.logger.addHandler(console_handler)

        # Create/update symlink to latest log
        if self.latest_link.exists() or self.latest_link.is_symlink():
            self.latest_link.unlink()
        # Use relative path from latest dir to log file for symlink
        if log_type == "workflow":
            symlink_target = Path("../workflows") / f"{name}_{self.timestamp}.log"
        else:
            symlink_target = Path("../agents") / f"{name}_{self.timestamp}.log"
        self.latest_link.symlink_to(symlink_target)

        # Log initialization (use str representation to avoid Path.cwd() issues)
        self.logger.info(f"[bold cyan]{'=' * 80}[/bold cyan]")
        self.logger.info(f"[bold green]{name.upper()} - Started[/bold green]")
        self.logger.info(f"[cyan]Timestamp: {self.timestamp}[/cyan]")
        self.logger.info(f"[bold cyan]{'=' * 80}[/bold cyan]")

    def debug(self, message: str):
        """Log debug message (file only)"""
        self.logger.debug(message)

    def info(self, message: str):
        """Log info message (file + console)"""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message (file + console)"""
        self.logger.warning(f"[yellow]{message}[/yellow]")

    def error(self, message: str):
        """Log error message (file + console)"""
        self.logger.error(f"[red]{message}[/red]")

    def success(self, message: str):
        """Log success message (file + console)"""
        self.logger.info(f"[bold green]✅ {message}[/bold green]")

    def section(self, title: str):
        """Log section header"""
        self.logger.info("")
        self.logger.info(f"[bold blue]{'─' * 80}[/bold blue]")
        self.logger.info(f"[bold blue]  {title}[/bold blue]")
        self.logger.info(f"[bold blue]{'─' * 80}[/bold blue]")
        self.logger.info("")

    def agent_start(self, agent_name: str, task_description: str):
        """Log agent start"""
        self.section(f"🤖 {agent_name} - Starting")
        self.info(f"[cyan]Task: {task_description[:100]}...[/cyan]")

    def agent_complete(self, agent_name: str, output_preview: str):
        """Log agent completion"""
        self.success(f"{agent_name} - Completed")
        self.debug(f"Output preview: {output_preview[:200]}...")

    def agent_error(self, agent_name: str, error: Exception):
        """Log agent error"""
        self.error(f"{agent_name} - Failed: {str(error)}")
        self.logger.exception(error)

    def workflow_complete(self, duration_seconds: float):
        """Log workflow completion"""
        self.section("🎉 Workflow Complete")
        self.success(f"Duration: {duration_seconds:.2f} seconds")
        self.info(f"[cyan]Full log: {self.log_file}[/cyan]")

    def close(self):
        """Close logger and cleanup old logs"""
        self.logger.info(f"[bold cyan]{'=' * 80}[/bold cyan]")
        self.logger.info(f"[bold green]{self.name.upper()} - Finished[/bold green]")
        self.logger.info(f"[bold cyan]{'=' * 80}[/bold cyan]")

        # Close handlers
        for handler in self.logger.handlers:
            handler.close()

        # Cleanup old logs (keep last 10)
        self._cleanup_old_logs()

    def _cleanup_old_logs(self):
        """Remove old log files, keeping most recent 10"""
        if self.log_type == "workflow":
            log_dir = self.workflow_dir
            pattern = f"{self.name}_*.log"
        else:
            log_dir = self.agent_dir
            pattern = f"{self.name}_*.log"

        log_files = sorted(log_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

        # Keep only the 10 most recent
        for old_log in log_files[10:]:
            try:
                old_log.unlink()
                self.logger.debug(f"Cleaned up old log: {old_log.name}")
            except Exception as e:
                self.logger.debug(f"Failed to cleanup {old_log.name}: {e}")


def get_logger(name: str, log_type: str = "workflow") -> CrewLogger:
    """
    Get or create a CrewLogger instance

    Args:
        name: Logger name
        log_type: "workflow" or "agent"

    Returns:
        CrewLogger instance
    """
    return CrewLogger(name, log_type)


# Example usage
if __name__ == "__main__":
    # Workflow logger
    logger = get_logger("phase2_incremental", "workflow")

    logger.section("Step 1: Detect API Changes")
    logger.info("Fetching OpenAPI spec from backend")
    logger.info("Loading previous API snapshot")
    logger.success("Detected 3 changed endpoints")

    logger.agent_start("ARCHITECT", "Design test scenarios for /api/matches")
    logger.info("Reading OpenAPI spec for /api/matches")
    logger.info("Analyzing endpoint parameters and responses")
    logger.agent_complete("ARCHITECT", "Generated 10 test scenarios covering happy path, errors, edge cases")

    logger.agent_start("MOCKER", "Generate test data based on ARCHITECT scenarios")
    logger.agent_complete("MOCKER", "Created 5 pytest fixtures with realistic data")

    logger.warning("Some tests may fail due to missing authentication")

    logger.workflow_complete(42.5)
    logger.close()

    print(f"\n✅ Log saved to: {logger.log_file}")
    print(f"📂 Latest log: {logger.latest_link}")
