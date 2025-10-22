"""
Template management for message templates.
"""

import json
from pathlib import Path
from typing import Any


class TemplateManager:
    """Manages message templates."""

    def __init__(self, templates_dir: str | None = None):
        """
        Initialize template manager.

        Args:
            templates_dir: Directory containing templates. Defaults to package templates.
        """
        if templates_dir is None:
            templates_dir = str(Path(__file__).parent.parent / "templates")

        self.templates_dir = Path(templates_dir)

    def list_templates(self) -> list[str]:
        """
        List available templates.

        Returns:
            List of template names (without .json extension)
        """
        if not self.templates_dir.exists():
            return []

        templates = []
        for file in self.templates_dir.glob("*.json"):
            templates.append(file.stem)

        return sorted(templates)

    def load_template(self, template_name: str) -> dict[str, Any] | None:
        """
        Load a template by name.

        Args:
            template_name: Template name (without .json extension)

        Returns:
            Template data or None if not found
        """
        template_path = self.templates_dir / f"{template_name}.json"

        if not template_path.exists():
            return None

        with open(template_path) as f:
            return json.load(f)

    def save_template(self, template_name: str, data: dict[str, Any]) -> bool:
        """
        Save a template.

        Args:
            template_name: Template name (without .json extension)
            data: Template data

        Returns:
            True if saved successfully
        """
        try:
            self.templates_dir.mkdir(parents=True, exist_ok=True)

            template_path = self.templates_dir / f"{template_name}.json"

            with open(template_path, "w") as f:
                json.dump(data, f, indent=2)

            return True

        except Exception:
            return False

    def template_exists(self, template_name: str) -> bool:
        """
        Check if a template exists.

        Args:
            template_name: Template name (without .json extension)

        Returns:
            True if template exists
        """
        template_path = self.templates_dir / f"{template_name}.json"
        return template_path.exists()
