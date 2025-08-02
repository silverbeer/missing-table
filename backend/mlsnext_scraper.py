#!/usr/bin/env python3
"""
MLS Next U13 Schedule Scraper

This script scrapes game schedules and scores from the MLS Next website
for U13 division and outputs the data to a CSV file.
"""

import asyncio
import csv
from datetime import datetime, timedelta

from playwright.async_api import async_playwright


class MLSNextScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.base_url = "https://www.mlssoccer.com/mlsnext/schedule/u13/"
        self.games_data = []

    async def scrape_games(
        self, match_date: str = None, club: str = None, division: str = "Northeast"
    ):
        """
        Scrape games from MLS Next website

        Args:
            match_date: Date in YYYY-MM-DD format (defaults to current date)
            club: Club name to filter by (optional)
            division: Division name (defaults to "Northeast")
        """
        if not match_date:
            match_date = datetime.now().strftime("%Y-%m-%d")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            try:
                print("🌐 Navigating to MLS Next U13 schedule page...")

                # Set longer timeout and user agent
                await page.set_extra_http_headers(
                    {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )

                # Try multiple wait strategies
                try:
                    await page.goto(self.base_url, timeout=60000, wait_until="domcontentloaded")
                except:
                    print("🔄 Retrying with different wait strategy...")
                    await page.goto(self.base_url, timeout=60000, wait_until="load")

                # Wait for page to load
                await page.wait_for_timeout(5000)

                # Check if page loaded successfully
                title = await page.title()
                print(f"📄 Page title: {title}")

                # Handle cookie consent if present
                await self._handle_cookie_consent(page)

                # Take a screenshot for debugging
                await page.screenshot(path="mlsnext_page.png")
                print("📸 Screenshot saved as mlsnext_page.png")

                # Try to extract games from current page first
                print("🔍 Looking for games on current page...")
                games = await self._extract_games(page)

                if not games:
                    print("📅 No games found, trying to set filters...")
                    await self._set_match_date(page, match_date)

                    if division:
                        print(f"🏆 Setting division to: {division}")
                        await self._set_division(page, division)

                    if club:
                        print(f"🏟️ Setting club to: {club}")
                        await self._set_club(page, club)

                    # Apply filters and wait for results
                    await self._apply_filters(page)

                    # Extract game data after filtering
                    games = await self._extract_games(page)

                self.games_data.extend(games)

                print(f"✅ Found {len(games)} games for {match_date}")

            except Exception as e:
                print(f"❌ Error scraping games: {e}")

            finally:
                await browser.close()

    async def _handle_cookie_consent(self, page):
        """Handle cookie consent dialog if present"""
        try:
            # Look for cookie consent buttons
            consent_buttons = [
                'button:has-text("Accept & Continue")',
                'button:has-text("Accept")',
                'button:has-text("Continue")',
                'button[id*="accept"]',
                'button[class*="accept"]',
            ]

            for button_selector in consent_buttons:
                buttons = page.locator(button_selector)
                if await buttons.count() > 0:
                    await buttons.first.click()
                    await page.wait_for_timeout(2000)
                    print("✅ Cookie consent accepted")
                    return

        except Exception as e:
            print(f"⚠️ Could not handle cookie consent: {e}")

    async def _set_match_date(self, page, match_date: str):
        """Set the match date filter by clicking on the date field and selecting from calendar"""
        try:
            # First, look for any clickable date field
            date_selectors = [
                'input[placeholder*="Match Date"]',
                'input[placeholder*="date"]',
                'input[type="date"]',
                'div[class*="date"]',
                'button[class*="date"]',
                '[data-testid*="date"]',
                ".date-picker",
                ".date-input",
                'input[name*="date"]',
            ]

            date_field_found = False
            for selector in date_selectors:
                date_field = page.locator(selector).first
                if await date_field.count() > 0:
                    print(f"📅 Found date field with selector: {selector}")
                    date_field_found = True

                    # Click on the date field to open calendar
                    await date_field.click()
                    await page.wait_for_timeout(1000)
                    print("📆 Clicked on date field, waiting for calendar...")

                    # Take screenshot to see calendar
                    await page.screenshot(path="calendar_open.png")
                    print("📸 Calendar screenshot saved")

                    # Try to find and click on day 1 of the month
                    await self._select_date_from_calendar(page, match_date)
                    break

            if not date_field_found:
                print("⚠️ Date input field not found, trying alternative approach...")
                # Try to find any element with "Match Date" text and click it
                match_date_elements = page.locator('text="Match Date"')
                if await match_date_elements.count() > 0:
                    print("📅 Found 'Match Date' text, clicking nearby input...")
                    parent = match_date_elements.first.locator("..")
                    inputs = parent.locator("input")
                    if await inputs.count() > 0:
                        await inputs.first.click()
                        await page.wait_for_timeout(1000)
                        await self._select_date_from_calendar(page, match_date)

        except Exception as e:
            print(f"⚠️ Could not set date: {e}")

    async def _select_date_from_calendar(self, page, match_date: str):
        """Select a date from the calendar picker"""
        try:
            # Parse the target date
            from datetime import datetime

            target_date = datetime.strptime(match_date, "%Y-%m-%d")
            target_day = target_date.day
            target_month = target_date.strftime("%B")
            target_year = target_date.year

            print(f"📅 Looking for date: {target_month} {target_day}, {target_year}")

            # Wait for calendar to appear
            await page.wait_for_timeout(1000)

            # Common calendar navigation selectors
            # First, try to navigate to correct month/year if needed
            month_year_selectors = [
                ".calendar-header",
                ".date-picker-header",
                '[class*="month"]',
                '[class*="year"]',
            ]

            # Look for day selectors - usually the 1st of the month
            day_selectors = [
                f'button:has-text("{target_day}")',
                f'div:has-text("{target_day}")',
                f'td:has-text("{target_day}")',
                f'[aria-label*="{target_day}"]',
                f'.calendar-day:has-text("{target_day}")',
                f'[data-day="{target_day}"]',
                f'span:has-text("{target_day}")',
            ]

            # Try to click on the specific day
            for selector in day_selectors:
                days = page.locator(selector)
                count = await days.count()
                if count > 0:
                    print(f"📅 Found {count} day elements with selector: {selector}")
                    # Click the first occurrence (usually the right one)
                    await days.first.click()
                    await page.wait_for_timeout(1000)
                    print(f"✅ Clicked on day {target_day}")
                    return

            print(f"⚠️ Could not find day {target_day} in calendar")

        except Exception as e:
            print(f"⚠️ Error selecting date from calendar: {e}")

    async def _set_division(self, page, division: str):
        """Set the division filter"""
        try:
            # Look for division dropdown or select
            division_selectors = [
                'select[name*="division"], select[id*="division"]',
                'div[class*="division"] select',
                f'select option:has-text("{division}")',
                f'button:has-text("{division}")',
                f'div:has-text("{division}")',
            ]

            for selector in division_selectors:
                elements = page.locator(selector)
                if await elements.count() > 0:
                    if "select" in selector:
                        await elements.first.select_option(label=division)
                    else:
                        await elements.first.click()
                    await page.wait_for_timeout(1000)
                    print(f"✅ Division set to: {division}")
                    return

            print("⚠️ Division selector not found")
        except Exception as e:
            print(f"⚠️ Could not set division: {e}")

    async def _set_club(self, page, club: str):
        """Set the club filter"""
        try:
            # Look for club dropdown or select
            club_selectors = [
                'select[name*="club"], select[id*="club"]',
                'div[class*="club"] select',
                f'select option:has-text("{club}")',
                f'button:has-text("{club}")',
                'input[placeholder*="club"]',
            ]

            for selector in club_selectors:
                elements = page.locator(selector)
                if await elements.count() > 0:
                    if "select" in selector:
                        await elements.first.select_option(label=club)
                    elif "input" in selector:
                        await elements.first.fill(club)
                    else:
                        await elements.first.click()
                    await page.wait_for_timeout(1000)
                    print(f"✅ Club set to: {club}")
                    return

            print("⚠️ Club selector not found")
        except Exception as e:
            print(f"⚠️ Could not set club: {e}")

    async def _apply_filters(self, page):
        """Apply the filters and wait for results"""
        try:
            # Force click the filter button even if not visible
            filter_button = page.locator('button[id="filter-btn-handler"]')
            if await filter_button.count() > 0:
                print("🔘 Found filter button, forcing click...")
                # Use JavaScript to force click
                await page.evaluate("document.getElementById('filter-btn-handler').click()")
                await page.wait_for_timeout(3000)

                # Take screenshot after filter click
                await page.screenshot(path="after_filter_click.png")
                print("📸 Screenshot after filter click saved")

                # Now look for date and division inputs
                await self._force_set_filters(page)

            # Wait for any dynamic content to load
            await page.wait_for_timeout(5000)
            print("✅ Waiting for dynamic content to load")

        except Exception as e:
            print(f"⚠️ Could not apply filters: {e}")

    async def _force_set_filters(self, page):
        """Force set filters using JavaScript if needed"""
        try:
            # Wait a bit for filter panel to fully render
            await page.wait_for_timeout(2000)

            # Look for all inputs in the filter panel
            all_inputs = await page.query_selector_all("input")
            print(f"📊 Found {len(all_inputs)} input elements on page")

            # Look specifically for Match Date input
            for i, input_elem in enumerate(all_inputs):
                placeholder = await page.evaluate("input => input.placeholder", input_elem)
                input_type = await page.evaluate("input => input.type", input_elem)
                name = await page.evaluate("input => input.name", input_elem)

                if placeholder and "match date" in placeholder.lower():
                    print(f"📅 Found Match Date input! Placeholder: {placeholder}")
                    # Click on it to open date picker
                    await page.evaluate("input => input.click()", input_elem)
                    await page.wait_for_timeout(1000)

                    # Take screenshot of date picker
                    await page.screenshot(path="date_picker_open.png")
                    print("📸 Date picker screenshot saved")

                    # Try to select date
                    await self._select_date_from_calendar(page, "2024-12-01")
                    break
                elif input_type == "text" and i < 5:  # Check first few text inputs
                    print(
                        f"   Input {i}: type={input_type}, name={name}, placeholder={placeholder}"
                    )

            # Look for division dropdown
            all_selects = await page.query_selector_all("select")
            print(f"📊 Found {len(all_selects)} select elements")

            for select in all_selects:
                # Check if this is the division select
                first_option = await page.evaluate(
                    "select => select.options[0]?.text || ''", select
                )
                if "division" in first_option.lower() or "all" in first_option.lower():
                    options = await page.evaluate(
                        "select => Array.from(select.options).map(opt => opt.text)", select
                    )
                    print(f"🏆 Found select with options: {options[:5]}...")  # Show first 5 options

                    # Look for Northeast option
                    for idx, opt in enumerate(options):
                        if "northeast" in opt.lower():
                            print(f"✅ Selecting Northeast (option {idx})")
                            await page.evaluate(
                                f"select => {{ select.selectedIndex = {idx}; select.dispatchEvent(new Event('change')); }}",
                                select,
                            )
                            break

            # Wait a bit after setting filters
            await page.wait_for_timeout(2000)

            # Look for any visible games now
            await page.screenshot(path="after_filter_set.png")
            print("📸 Screenshot after filter set saved")

        except Exception as e:
            print(f"⚠️ Error in force set filters: {e}")

    async def _extract_games(self, page):
        """Extract game data from the page"""
        games = []

        try:
            # Wait for page to load completely
            await page.wait_for_timeout(3000)

            # Try to scroll down to load any lazy-loaded content
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            # Look for game containers with expanded selectors
            game_selectors = [
                'div[class*="game"]',
                'div[class*="match"]',
                'div[class*="fixture"]',
                'div[class*="schedule"]',
                'tr[class*="game"]',
                'tr[class*="match"]',
                "table tr",
                ".schedule-item",
                ".game-item",
                ".match-item",
                '[data-testid*="game"]',
                '[data-testid*="match"]',
                'div[role="row"]',
                'li[class*="game"]',
                'article[class*="game"]',
            ]

            game_elements = None
            selector_used = None

            for selector in game_selectors:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    # Filter out elements that are too small (likely not games)
                    valid_elements = []
                    for i in range(count):
                        element = elements.nth(i)
                        text_content = await element.text_content()
                        if (
                            text_content and len(text_content.strip()) > 10
                        ):  # Has substantial content
                            valid_elements.append(element)

                    if valid_elements:
                        game_elements = valid_elements
                        selector_used = selector
                        print(
                            f"✅ Found {len(valid_elements)} potential game elements using selector: {selector}"
                        )
                        break

            if not game_elements:
                print("⚠️ No game elements found, trying comprehensive text extraction")
                return await self._extract_from_page_content(page)

            # Extract data from each game element
            for i, game_element in enumerate(game_elements):
                try:
                    game_data = await self._extract_single_game(game_element)
                    if game_data:
                        games.append(game_data)
                        print(
                            f"   📝 Game {i + 1}: {game_data.get('home_team', 'Unknown')} vs {game_data.get('away_team', 'Unknown')}"
                        )
                except Exception as e:
                    print(f"   ⚠️ Error extracting game {i + 1}: {e}")

        except Exception as e:
            print(f"⚠️ Error extracting games: {e}")

        return games

    async def _extract_single_game(self, game_element):
        """Extract data from a single game element"""
        try:
            # Try to extract game information using common patterns
            game_data = {
                "game_date": "",
                "home_team": "",
                "away_team": "",
                "home_score": "",
                "away_score": "",
                "status": "",
            }

            # Get all text content from the game element
            text_content = await game_element.text_content()

            # Look for team names (usually the longest text elements)
            team_elements = game_element.locator("div, span, td").filter(
                has_text=lambda text: len(text.strip()) > 3
            )
            team_count = await team_elements.count()

            teams = []
            scores = []

            for i in range(team_count):
                element_text = await team_elements.nth(i).text_content()
                element_text = element_text.strip()

                # Check if it's a score (number)
                if element_text.isdigit():
                    scores.append(int(element_text))
                # Check if it's a team name (contains letters and is substantial)
                elif len(element_text) > 2 and any(c.isalpha() for c in element_text):
                    teams.append(element_text)

            # Try to match teams and scores
            if len(teams) >= 2:
                game_data["home_team"] = teams[0]
                game_data["away_team"] = teams[1]

            if len(scores) >= 2:
                game_data["home_score"] = scores[0]
                game_data["away_score"] = scores[1]

            # Try to extract date from the element or use current date
            date_text = await self._extract_date_from_element(game_element)
            game_data["game_date"] = date_text or datetime.now().strftime("%Y-%m-%d")

            # Only return if we have at least team names
            if game_data["home_team"] and game_data["away_team"]:
                return game_data

        except Exception as e:
            print(f"⚠️ Error extracting single game: {e}")

        return None

    async def _extract_date_from_element(self, element):
        """Try to extract date from game element"""
        try:
            text = await element.text_content()
            # Look for date patterns in text
            import re

            date_patterns = [
                r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
                r"\d{1,2}/\d{1,2}/\d{4}",  # MM/DD/YYYY
                r"\d{1,2}-\d{1,2}-\d{4}",  # MM-DD-YYYY
            ]

            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group()

        except:
            pass
        return None

    async def _extract_from_page_content(self, page):
        """Comprehensive method to extract games from page content"""
        games = []
        print("🔍 Attempting comprehensive page content extraction...")

        try:
            # Get all text content from the page
            content = await page.content()
            visible_text = await page.evaluate("document.body.innerText")

            # Save content for debugging
            with open("page_content.txt", "w", encoding="utf-8") as f:
                f.write(visible_text)
            print("📄 Saved page content to page_content.txt for analysis")

            # Look for patterns that might indicate games
            import re

            # Pattern for team names vs team names with scores
            # Examples: "Team A 2 - 1 Team B", "Team A vs Team B", etc.
            game_patterns = [
                r"([A-Za-z\s]+)\s+(\d+)\s*[-–—]\s*(\d+)\s+([A-Za-z\s]+)",  # Team A 2-1 Team B
                r"([A-Za-z\s]+)\s+vs\.?\s+([A-Za-z\s]+)\s*[:\s]*(\d+)?\s*[-–—]?\s*(\d+)?",  # Team A vs Team B 2-1
            ]

            for pattern in game_patterns:
                matches = re.finditer(pattern, visible_text, re.MULTILINE | re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    if len(groups) >= 4:
                        game_data = {
                            "game_date": datetime.now().strftime("%Y-%m-%d"),
                            "home_team": groups[0].strip(),
                            "away_team": groups[3].strip()
                            if len(groups) > 3
                            else groups[1].strip(),
                            "home_score": groups[1] if groups[1] and groups[1].isdigit() else "",
                            "away_score": groups[2] if groups[2] and groups[2].isdigit() else "",
                            "status": "extracted",
                        }

                        # Filter out obvious non-team names
                        if (
                            len(game_data["home_team"]) > 2
                            and len(game_data["away_team"]) > 2
                            and not any(
                                word in game_data["home_team"].lower()
                                for word in ["schedule", "scores", "filter", "search"]
                            )
                        ):
                            games.append(game_data)

        except Exception as e:
            print(f"⚠️ Error in comprehensive extraction: {e}")

        return games

    def _extract_from_text(self, content: str):
        """Legacy fallback method"""
        print("⚠️ Using legacy fallback text extraction method")
        return []

    async def scrape_date_range(
        self, start_date: str, end_date: str, club: str = None, division: str = "Northeast"
    ):
        """Scrape games for a date range"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        current_date = start
        while current_date <= end:
            date_str = current_date.strftime("%Y-%m-%d")
            print(f"\n📅 Scraping games for {date_str}")

            await self.scrape_games(match_date=date_str, club=club, division=division)

            current_date += timedelta(days=1)
            # Add delay between requests to be respectful
            await asyncio.sleep(2)

    def save_to_csv(self, filename: str = None):
        """Save scraped games to CSV file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mlsnext_u13_games_{timestamp}.csv"

        if not self.games_data:
            print("⚠️ No games data to save")
            return

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "game_date",
                "home_team",
                "away_team",
                "home_score",
                "away_score",
                "status",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for game in self.games_data:
                writer.writerow(game)

        print(f"💾 Saved {len(self.games_data)} games to {filename}")

    def print_summary(self):
        """Print summary of scraped data"""
        if not self.games_data:
            print("📊 No games found")
            return

        print("\n📊 Scraping Summary:")
        print(f"   Total games found: {len(self.games_data)}")

        # Count by date
        dates = {}
        for game in self.games_data:
            date = game.get("game_date", "Unknown")
            dates[date] = dates.get(date, 0) + 1

        print("   Games by date:")
        for date, count in sorted(dates.items()):
            print(f"     {date}: {count} games")


async def main():
    """Main function to run the scraper"""
    scraper = MLSNextScraper(headless=False)  # Set to True for headless mode

    try:
        # Example usage: scrape games for the 1st of December 2024
        await scraper.scrape_games(
            match_date="2024-12-01",  # Using 1st of the month for easier calendar selection
            division="Northeast",
        )

        # Or scrape a date range (uncomment to use)
        # await scraper.scrape_date_range(
        #     start_date="2024-12-01",
        #     end_date="2024-12-07",
        #     division="Northeast"
        # )

        # Print summary and save to CSV
        scraper.print_summary()
        scraper.save_to_csv()

    except Exception as e:
        print(f"❌ Error in main: {e}")


if __name__ == "__main__":
    asyncio.run(main())
