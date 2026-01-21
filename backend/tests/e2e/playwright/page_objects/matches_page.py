"""
Matches Page Object for Missing Table match schedules and results.

Handles:
- Match list display
- Filtering by date, team, season
- Match details view
- Score updates (for authenticated users)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .base_page import BasePage

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)


@dataclass
class Match:
    """Data class representing a match."""

    id: str | None
    date: str
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    venue: str | None
    status: str  # scheduled, completed, cancelled


class MatchesPage(BasePage):
    """
    Page Object for the Matches page.

    Usage:
        def test_matches_display(matches_page):
            matches_page.navigate()
            matches = matches_page.get_matches()
            assert len(matches) > 0
    """

    URL_PATH = "/matches"
    PAGE_TITLE = "Matches"
    LOAD_INDICATOR = ".matches-list, [data-testid='matches-list'], .match-card"

    # Filters
    SEASON_FILTER = "select[name='season'], #season-filter"
    AGE_GROUP_FILTER = "select[name='age_group'], #age-group-filter"
    TEAM_FILTER = "input[name='team'], #team-filter, [data-testid='team-search']"
    DATE_FROM = "input[name='date_from'], #date-from, [data-testid='date-from']"
    DATE_TO = "input[name='date_to'], #date-to, [data-testid='date-to']"

    # Match list
    MATCH_LIST = ".matches-list, [data-testid='matches-list']"
    MATCH_CARDS = ".match-card, [data-testid='match-card'], .match-item"

    # Match card elements
    MATCH_DATE = ".match-date, [data-testid='match-date']"
    HOME_TEAM = ".home-team, [data-testid='home-team']"
    AWAY_TEAM = ".away-team, [data-testid='away-team']"
    HOME_SCORE = ".home-score, [data-testid='home-score']"
    AWAY_SCORE = ".away-score, [data-testid='away-score']"
    MATCH_VENUE = ".venue, [data-testid='venue']"
    MATCH_STATUS = ".status, [data-testid='match-status']"

    # Pagination
    NEXT_PAGE = "button:has-text('Next'), [data-testid='next-page']"
    PREV_PAGE = "button:has-text('Previous'), [data-testid='prev-page']"
    PAGE_INFO = ".page-info, [data-testid='page-info']"

    # Messages
    NO_MATCHES = "text=No matches, .empty-state"
    LOADING = ".loading, .spinner"

    def __init__(self, page: Page, base_url: str = "http://localhost:8080") -> None:
        super().__init__(page, base_url)

    # =========================================================================
    # Filter Actions
    # =========================================================================

    def filter_by_season(self, season: str) -> MatchesPage:
        """Filter matches by season."""
        logger.info(f"Filtering by season: {season}")
        self.select_option(self.SEASON_FILTER, label=season)
        self.wait_for_matches_update()
        return self

    def filter_by_age_group(self, age_group: str) -> MatchesPage:
        """Filter matches by age group."""
        logger.info(f"Filtering by age group: {age_group}")
        self.select_option(self.AGE_GROUP_FILTER, label=age_group)
        self.wait_for_matches_update()
        return self

    def search_team(self, team_name: str) -> MatchesPage:
        """Search for matches involving a specific team."""
        logger.info(f"Searching for team: {team_name}")
        self.fill(self.TEAM_FILTER, team_name)
        self.press_enter()
        self.wait_for_matches_update()
        return self

    def set_date_range(self, from_date: str, to_date: str) -> MatchesPage:
        """Set date range filter."""
        logger.info(f"Setting date range: {from_date} to {to_date}")
        self.fill(self.DATE_FROM, from_date)
        self.fill(self.DATE_TO, to_date)
        self.wait_for_matches_update()
        return self

    def clear_filters(self) -> MatchesPage:
        """Clear all filters."""
        logger.info("Clearing all filters")
        # Clear text inputs
        if self.is_visible(self.TEAM_FILTER):
            self.page.locator(self.TEAM_FILTER).clear()
        if self.is_visible(self.DATE_FROM):
            self.page.locator(self.DATE_FROM).clear()
        if self.is_visible(self.DATE_TO):
            self.page.locator(self.DATE_TO).clear()
        self.wait_for_matches_update()
        return self

    def wait_for_matches_update(self) -> None:
        """Wait for matches list to update."""
        self.page.wait_for_timeout(500)
        self.wait_for_network_idle()

    # =========================================================================
    # Match Data Retrieval
    # =========================================================================

    def get_matches(self) -> list[Match]:
        """Get all matches displayed on current page."""
        logger.info("Getting matches data")
        matches = []

        cards = self.page.locator(self.MATCH_CARDS)
        count = cards.count()

        for i in range(count):
            card = cards.nth(i)
            try:
                match = Match(
                    id=card.get_attribute("data-match-id"),
                    date=self._get_text_or_empty(card, self.MATCH_DATE),
                    home_team=self._get_text_or_empty(card, self.HOME_TEAM),
                    away_team=self._get_text_or_empty(card, self.AWAY_TEAM),
                    home_score=self._parse_score(card, self.HOME_SCORE),
                    away_score=self._parse_score(card, self.AWAY_SCORE),
                    venue=self._get_text_or_empty(card, self.MATCH_VENUE),
                    status=self._determine_status(card),
                )
                matches.append(match)
            except Exception as e:
                logger.warning(f"Error parsing match {i}: {e}")
                continue

        return matches

    def get_match_count(self) -> int:
        """Get number of matches on current page."""
        return self.page.locator(self.MATCH_CARDS).count()

    def get_matches_for_team(self, team_name: str) -> list[Match]:
        """Get all matches involving a specific team."""
        matches = self.get_matches()
        return [
            m for m in matches if team_name.lower() in m.home_team.lower() or team_name.lower() in m.away_team.lower()
        ]

    def get_upcoming_matches(self) -> list[Match]:
        """Get matches that are scheduled (no scores yet)."""
        matches = self.get_matches()
        return [m for m in matches if m.status == "scheduled"]

    def get_completed_matches(self) -> list[Match]:
        """Get matches that have been completed."""
        matches = self.get_matches()
        return [m for m in matches if m.status == "completed"]

    # =========================================================================
    # Match Actions
    # =========================================================================

    def click_match(self, index: int = 0) -> None:
        """Click on a match card to view details."""
        logger.info(f"Clicking match at index {index}")
        cards = self.page.locator(self.MATCH_CARDS)
        cards.nth(index).click()
        self.page.wait_for_load_state("networkidle")

    def click_match_by_teams(self, home_team: str, away_team: str) -> None:
        """Click on match by team names."""
        logger.info(f"Clicking match: {home_team} vs {away_team}")
        matches = self.get_matches()
        for i, match in enumerate(matches):
            if home_team.lower() in match.home_team.lower() and away_team.lower() in match.away_team.lower():
                self.click_match(i)
                return
        raise ValueError(f"Match not found: {home_team} vs {away_team}")

    # =========================================================================
    # Pagination
    # =========================================================================

    def has_next_page(self) -> bool:
        """Check if there's a next page."""
        next_btn = self.page.locator(self.NEXT_PAGE)
        return next_btn.is_visible() and next_btn.is_enabled()

    def has_prev_page(self) -> bool:
        """Check if there's a previous page."""
        prev_btn = self.page.locator(self.PREV_PAGE)
        return prev_btn.is_visible() and prev_btn.is_enabled()

    def go_to_next_page(self) -> MatchesPage:
        """Navigate to next page of matches."""
        if self.has_next_page():
            self.click(self.NEXT_PAGE)
            self.wait_for_matches_update()
        return self

    def go_to_prev_page(self) -> MatchesPage:
        """Navigate to previous page of matches."""
        if self.has_prev_page():
            self.click(self.PREV_PAGE)
            self.wait_for_matches_update()
        return self

    # =========================================================================
    # State Queries
    # =========================================================================

    def is_matches_loaded(self) -> bool:
        """Check if matches list is loaded."""
        return self.is_visible(self.MATCH_LIST)

    def has_matches(self) -> bool:
        """Check if there are any matches displayed."""
        return self.get_match_count() > 0

    def has_no_matches_message(self) -> bool:
        """Check if no matches message is displayed."""
        return self.is_visible(self.NO_MATCHES)

    def is_loading(self) -> bool:
        """Check if matches are loading."""
        return self.is_visible(self.LOADING)

    # =========================================================================
    # Validation Helpers
    # =========================================================================

    def validate_matches_in_date_order(self, ascending: bool = True) -> bool:
        """Verify matches are sorted by date."""
        matches = self.get_matches()
        if len(matches) < 2:
            return True

        dates = [m.date for m in matches]
        if ascending:
            return dates == sorted(dates)
        else:
            return dates == sorted(dates, reverse=True)

    def validate_team_filter(self, team_name: str) -> bool:
        """Verify all displayed matches involve the specified team."""
        matches = self.get_matches()
        for match in matches:
            if team_name.lower() not in match.home_team.lower() and team_name.lower() not in match.away_team.lower():
                return False
        return True

    # =========================================================================
    # Utilities
    # =========================================================================

    def _get_text_or_empty(self, parent, selector: str) -> str:
        """Get text from element or empty string if not found."""
        element = parent.locator(selector)
        if element.count() > 0:
            return element.inner_text().strip()
        return ""

    def _parse_score(self, parent, selector: str) -> int | None:
        """Parse score from element."""
        text = self._get_text_or_empty(parent, selector)
        if text and text.isdigit():
            return int(text)
        return None

    def _determine_status(self, card) -> str:
        """Determine match status from card."""
        status_elem = card.locator(self.MATCH_STATUS)
        if status_elem.count() > 0:
            status_text = status_elem.inner_text().lower()
            if "completed" in status_text or "final" in status_text:
                return "completed"
            elif "cancelled" in status_text:
                return "cancelled"

        # Check if scores are present
        home_score = self._parse_score(card, self.HOME_SCORE)
        away_score = self._parse_score(card, self.AWAY_SCORE)

        if home_score is not None and away_score is not None:
            return "completed"
        return "scheduled"
