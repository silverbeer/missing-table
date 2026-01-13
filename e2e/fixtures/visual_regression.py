"""
Visual Regression Testing Utilities.

This module provides tools for visual regression testing,
comparing screenshots against baseline images to detect
unintended visual changes.

Features:
- Baseline screenshot management
- Pixel-by-pixel comparison
- Difference highlighting
- Threshold-based comparison (for dynamic content)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class VisualRegression:
    """
    Visual regression testing utility.
    
    Usage:
        def test_homepage_visual(page, visual_regression):
            page.goto("http://localhost:8080")
            assert visual_regression.compare("homepage")
    """
    
    def __init__(
        self,
        page: Page,
        baseline_dir: Path,
        diff_dir: Path,
        threshold: float = 0.01
    ) -> None:
        """
        Initialize visual regression tester.
        
        Args:
            page: Playwright page object
            baseline_dir: Directory for baseline screenshots
            diff_dir: Directory for diff images
            threshold: Allowed pixel difference ratio (0.0 to 1.0)
        """
        self.page = page
        self.baseline_dir = baseline_dir
        self.diff_dir = diff_dir
        self.threshold = threshold
        
        # Ensure directories exist
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.diff_dir.mkdir(parents=True, exist_ok=True)

    def compare(
        self,
        name: str,
        full_page: bool = True,
        element: str | None = None,
        update_baseline: bool = False
    ) -> bool:
        """
        Compare current screenshot against baseline.
        
        Args:
            name: Unique name for this screenshot
            full_page: Capture full page (scrollable)
            element: CSS selector for specific element
            update_baseline: Force update of baseline image
            
        Returns:
            True if images match (within threshold)
        """
        baseline_path = self.baseline_dir / f"{name}.png"
        current_path = self.diff_dir / f"{name}_current.png"
        diff_path = self.diff_dir / f"{name}_diff.png"
        
        # Take current screenshot
        if element:
            self.page.locator(element).screenshot(path=str(current_path))
        else:
            self.page.screenshot(path=str(current_path), full_page=full_page)
        
        # If no baseline or updating, save current as baseline
        if not baseline_path.exists() or update_baseline:
            logger.info(f"Creating baseline: {baseline_path}")
            current_path.rename(baseline_path)
            return True
        
        # Compare images
        try:
            from PIL import Image
            
            baseline = Image.open(baseline_path)
            current = Image.open(current_path)
            
            # Check dimensions
            if baseline.size != current.size:
                logger.error(
                    f"Size mismatch: baseline {baseline.size} vs current {current.size}"
                )
                return False
            
            # Calculate difference
            diff_count = 0
            total_pixels = baseline.size[0] * baseline.size[1]
            
            baseline_pixels = baseline.load()
            current_pixels = current.load()
            
            diff_image = Image.new("RGB", baseline.size)
            diff_pixels = diff_image.load()
            
            for x in range(baseline.size[0]):
                for y in range(baseline.size[1]):
                    if baseline_pixels[x, y] != current_pixels[x, y]:
                        diff_count += 1
                        diff_pixels[x, y] = (255, 0, 0)  # Red for difference
                    else:
                        diff_pixels[x, y] = current_pixels[x, y]
            
            diff_ratio = diff_count / total_pixels
            
            if diff_ratio > self.threshold:
                # Save diff image
                diff_image.save(str(diff_path))
                logger.error(
                    f"Visual difference detected: {diff_ratio:.2%} "
                    f"(threshold: {self.threshold:.2%})"
                )
                logger.error(f"Diff saved to: {diff_path}")
                return False
            
            logger.info(f"Visual match: {name} ({diff_ratio:.2%} difference)")
            return True
            
        except ImportError:
            logger.warning("PIL not installed, skipping pixel comparison")
            return True
        except Exception as e:
            logger.error(f"Visual comparison failed: {e}")
            return False

    def update_all_baselines(self) -> None:
        """Update all baseline screenshots with current state."""
        logger.info("Updating all baselines from diff directory")
        for diff_file in self.diff_dir.glob("*_current.png"):
            name = diff_file.stem.replace("_current", "")
            baseline_path = self.baseline_dir / f"{name}.png"
            diff_file.rename(baseline_path)
            logger.info(f"Updated baseline: {name}")

    def get_baseline_names(self) -> list[str]:
        """Get list of all baseline screenshot names."""
        return [
            p.stem for p in self.baseline_dir.glob("*.png")
        ]

    def cleanup_diffs(self) -> None:
        """Remove all diff images."""
        for diff_file in self.diff_dir.glob("*.png"):
            diff_file.unlink()
        logger.info("Cleaned up diff directory")
