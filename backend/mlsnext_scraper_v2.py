#!/usr/bin/env python3
"""
MLS Next U13 Schedule Scraper V2 - Direct filter interaction

This script scrapes game schedules and scores from the MLS Next website
for U13 division and outputs the data to a CSV file.
"""

import asyncio
import csv
from datetime import datetime

from playwright.async_api import async_playwright


class MLSNextScraperV2:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.base_url = "https://www.mlssoccer.com/mlsnext/schedule/u13/"
        self.games_data = []

    async def scrape_games(
        self, match_date: str = None, club: str = None, division: str = "Northeast"
    ):
        """
        Scrape games from MLS Next website

        Args:
            match_date: Date in YYYY-MM-DD format
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

                # Set user agent
                await page.set_extra_http_headers(
                    {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )

                await page.goto(self.base_url, timeout=60000, wait_until="domcontentloaded")
                print("⏳ Waiting for page and cookie consent to load...")
                await page.wait_for_timeout(10000)  # Give more time for cookie consent to appear

                # Handle cookie consent if present
                await self._handle_cookie_consent(page)

                print("📄 Page loaded, waiting for filters to be ready...")
                await page.wait_for_timeout(3000)

                # Take initial screenshot
                await page.screenshot(path="mlsnext_initial.png")
                print("📸 Initial screenshot saved")

                # First, try to dismiss any overlays that might interfere
                await self._dismiss_overlays(page)

                # Ensure we're on U13 page
                print("🎯 Ensuring we're on U13 schedule...")
                await self._ensure_u13_selected(page)

                # Look for and click the Match Date field
                print("📅 Looking for Match Date field...")
                await self._select_september_2024_range(page)

                # Set Division dropdown
                if division:
                    print("🏆 Looking for division dropdown...")

                    # Find all select elements and check which one has division options
                    selects = await page.query_selector_all("select")
                    for select_elem in selects:
                        try:
                            # Get all options for this select
                            options = await select_elem.evaluate(
                                "el => Array.from(el.options).map(opt => opt.text)"
                            )

                            # Check if this select has division options
                            if any("northeast" in opt.lower() for opt in options):
                                print(f"✅ Found division dropdown with options: {options[:3]}...")

                                # Select Northeast
                                await select_elem.evaluate(
                                    """
                                    (select, targetDivision) => {
                                        for (let i = 0; i < select.options.length; i++) {
                                            if (select.options[i].text.toLowerCase().includes(targetDivision.toLowerCase())) {
                                                select.selectedIndex = i;
                                                select.dispatchEvent(new Event('change', { bubbles: true }));
                                                break;
                                            }
                                        }
                                    }
                                """,
                                    division,
                                )

                                print(f"✅ Division set to: {division}")
                                await page.wait_for_timeout(3000)
                                break
                        except:
                            continue

                # Set Club if provided
                if club:
                    print(f"🏟️ Setting club to: {club}")
                    club_dropdown = page.locator('div:has-text("Club") + div select, select').nth(
                        1
                    )  # Usually the 2nd dropdown
                    if await club_dropdown.count() > 0:
                        await club_dropdown.select_option(label=club)
                        print(f"✅ Club set to: {club}")
                        await page.wait_for_timeout(2000)

                # Wait for results to load
                print("⏳ Waiting for results to load...")
                await page.wait_for_timeout(5000)

                # Take screenshot of results
                await page.screenshot(path="mlsnext_results.png")
                print("📸 Results screenshot saved")

                # Extract game data
                games = await self._extract_games(page)
                self.games_data.extend(games)

                print(f"✅ Found {len(games)} games")

            except Exception as e:
                print(f"❌ Error scraping games: {e}")

            finally:
                await browser.close()

    async def _handle_cookie_consent(self, page):
        """Handle cookie consent dialog if present"""
        try:
            print("🍪 Looking for cookie consent dialog...")
            # Wait for cookie dialog to appear - use the specific ID
            accept_button = page.locator("#onetrust-accept-btn-handler")

            # Check if button exists and is visible
            if await accept_button.count() > 0:
                # Wait for it to be visible
                await accept_button.wait_for(state="visible", timeout=10000)
                print("🍪 Cookie consent dialog found, accepting...")
                await accept_button.click()
                print("✅ Cookie consent accepted")

                # Wait for the page to reload/update after accepting cookies
                print("⏳ Waiting for page to update after cookie acceptance...")
                await page.wait_for_timeout(7000)  # Give more time for page to settle

                # Take screenshot after cookie acceptance
                await page.screenshot(path="after_cookie_accept.png")
                print("📸 Screenshot after cookie acceptance saved")

                # Wait for filter controls to be visible
                try:
                    await page.wait_for_selector('text="Match Date"', timeout=15000)
                    print("✅ Filter controls loaded")
                except:
                    print("⚠️ Filter controls not found after cookie acceptance")
            else:
                print("ℹ️ No cookie consent dialog found")
        except Exception as e:
            print(f"ℹ️ Cookie consent handling: {e}")

    async def _dismiss_overlays(self, page):
        """Dismiss any overlays that might interfere with clicking"""
        try:
            # Look for common overlay close buttons
            overlay_selectors = [
                'button[aria-label="Close"]',
                ".close-button",
                "[data-dismiss]",
                'button:has-text("×")',
                'button:has-text("✕")',
            ]

            for selector in overlay_selectors:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    try:
                        await elements.first.click(timeout=2000)
                        print(f"✅ Dismissed overlay using: {selector}")
                        await page.wait_for_timeout(1000)
                    except:
                        continue

            # Also try pressing Escape key to dismiss overlays
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1000)

        except Exception as e:
            print(f"ℹ️ Overlay dismissal: {e}")

    async def _ensure_u13_selected(self, page):
        """Ensure we're on the U13 schedule page"""
        try:
            # Click on U13 schedule tab if not already selected (use the first one which is in navigation)
            u13_tab = page.locator('text="U13 schedule"').first
            if await u13_tab.count() > 0:
                await u13_tab.click()
                print("✅ Clicked U13 schedule tab")
                await page.wait_for_timeout(3000)  # Give more time for page to change

            # Also set Age Group dropdown to U13 if it exists
            age_group_selects = await page.query_selector_all("select")
            for select in age_group_selects:
                try:
                    options = await select.evaluate(
                        "el => Array.from(el.options).map(opt => opt.text)"
                    )
                    if any("u13" in opt.lower() for opt in options):
                        await select.evaluate("""
                            (select) => {
                                for (let i = 0; i < select.options.length; i++) {
                                    if (select.options[i].text.toLowerCase().includes('u13')) {
                                        select.selectedIndex = i;
                                        select.dispatchEvent(new Event('change', { bubbles: true }));
                                        break;
                                    }
                                }
                            }
                        """)
                        print("✅ Set Age Group to U13")
                        await page.wait_for_timeout(1000)
                        break
                except:
                    continue

        except Exception as e:
            print(f"⚠️ Error ensuring U13 selected: {e}")

    async def _select_september_2024_range(self, page):
        """Select September 1-30, 2024 date range using iframe-based approach from Codegen"""
        try:
            print("📅 Step 1: Attempting to access iframe and click Match Date field...")

            # Try iframe approach first, with fallback to direct page access
            main_frame = None
            try:
                # Wait for iframe to be available
                await page.wait_for_selector("iframe", timeout=10000)
                main_frame = (
                    page.get_by_role("main", name="Page main content")
                    .locator("iframe")
                    .content_frame
                )

                # Click the Match Date textbox in iframe
                await main_frame.get_by_role("textbox", name="Match Date").click()
                print("✅ Clicked Match Date field in iframe")
                await page.wait_for_timeout(2000)

            except Exception as e:
                print(f"⚠️ Iframe approach failed: {e}")
                print("📅 Falling back to direct page approach...")

                # Fallback to direct page interaction
                date_elements = page.locator('*:has-text("2025")')
                if await date_elements.count() > 0:
                    await date_elements.first.click()
                    print("✅ Clicked date field using fallback")
                    await page.wait_for_timeout(2000)
                else:
                    print("❌ Could not find date field")
                    return

            # Take screenshot after opening calendar
            await page.screenshot(path="calendar_step1_opened.png")
            print("📸 Calendar opened screenshot saved")

            print("📅 Step 2: Navigating back to September 2024...")

            # Use JavaScript fallback for month navigation (our proven approach)
            for i in range(9):
                try:
                    await page.evaluate("""
                        // Look for any button that might be the previous month
                        const buttons = document.querySelectorAll('button, span');
                        for (let btn of buttons) {
                            if (btn.textContent.includes('❮') || btn.textContent.includes('<') || 
                                btn.getAttribute('aria-label')?.toLowerCase().includes('previous')) {
                                btn.click();
                                break;
                            }
                        }
                    """)
                    print(f"   ⬅️ Navigated back month {i + 1}/9")
                    await page.wait_for_timeout(500)
                except:
                    print(f"   ⚠️ Could not navigate month {i + 1}")

            # Take screenshot after navigation
            await page.screenshot(path="calendar_step2_september.png")
            print("📸 September 2024 calendar screenshot saved")

            print("📅 Step 3: Clicking on September 1st...")

            # Click on day 1 - try iframe first, then fallback
            try:
                if main_frame:
                    await main_frame.get_by_role("cell", name="1", exact=True).first.click()
                else:
                    day_1_element = page.locator('.daterangepicker td:has-text("1")').first
                    await day_1_element.click()
                print("✅ Clicked on September 1st")
                await page.wait_for_timeout(1000)
            except Exception as e:
                print(f"ℹ️ Day 1 selection: {e}")

            print("📅 Step 4: Clicking on September 30th...")

            # Click on day 30 - try iframe first, then fallback
            try:
                if main_frame:
                    await main_frame.get_by_role("cell", name="30").nth(1).click()
                else:
                    day_30_element = page.locator('.daterangepicker td:has-text("30")').first
                    await day_30_element.click()
                print("✅ Clicked on September 30th")
                await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"⚠️ Error clicking day 30: {e}")

            # Take screenshot after selecting range
            await page.screenshot(path="calendar_step4_range_selected.png")
            print("📸 Date range selected screenshot saved")

            print("📅 Step 5: Clicking Apply button...")

            # Click Apply button - try iframe first, then fallback
            try:
                if main_frame:
                    await main_frame.get_by_role("button", name="Apply").click()
                else:
                    apply_element = page.locator('button.applyBtn, button:has-text("Apply")').first
                    await apply_element.click()
                print("✅ Clicked Apply button")
                await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"⚠️ Error clicking Apply button: {e}")
                # Try forcing the apply button click
                try:
                    await page.evaluate("document.querySelector('button.applyBtn')?.click()")
                    print("✅ Forced Apply button click via JavaScript")
                    await page.wait_for_timeout(3000)
                except:
                    print("⚠️ Could not force Apply button click")

            # Take final screenshot
            await page.screenshot(path="calendar_step5_applied.png")
            print("📸 Final results screenshot saved")
            print("✅ September 1-30, 2024 date range selection completed")

        except Exception as e:
            print(f"❌ Error in date selection: {e}")

    async def _select_date_from_calendar(self, page, match_date: str):
        """Select a date from the calendar picker"""
        try:
            # Parse the target date
            target_date = datetime.strptime(match_date, "%Y-%m-%d")
            target_day = target_date.day
            target_month = target_date.strftime("%B")
            target_year = target_date.year

            print(f"📅 Selecting date: {target_month} {target_day}, {target_year}")

            # Navigate to correct month/year if needed
            # This will depend on the specific calendar implementation

            # Look for the day in the calendar
            # Try different selectors for calendar days
            day_selectors = [
                f'button:has-text("{target_day}")',
                f'td:has-text("{target_day}")',
                f'div[role="gridcell"]:has-text("{target_day}")',
                f'[aria-label*="{target_day}"]',
                f'span:text-is("{target_day}")',
            ]

            for selector in day_selectors:
                days = page.locator(selector)
                if await days.count() > 0:
                    # Click the first matching day
                    await days.first.click()
                    print(f"✅ Clicked on {target_month} {target_day}")
                    await page.wait_for_timeout(1000)
                    return

            print(f"⚠️ Could not find {target_day} in calendar")

        except Exception as e:
            print(f"⚠️ Error selecting date: {e}")

    async def _extract_games(self, page):
        """Extract game data from the results"""
        games = []

        try:
            # Wait for any loading to complete
            await page.wait_for_timeout(2000)

            # Check if "No data available" message is present
            no_data = page.locator('text="No data available"')
            if await no_data.count() > 0:
                print("ℹ️ No games found for selected filters")
                return games

            # Look for game rows in a table or list
            game_selectors = [
                "table tbody tr",
                'div[class*="game-row"]',
                'div[class*="match-row"]',
                'div[role="row"]:not(:has-text("Match Date"))',
                ".game-item",
                '[data-testid*="game"]',
            ]

            for selector in game_selectors:
                rows = page.locator(selector)
                count = await rows.count()
                if count > 0:
                    print(f"✅ Found {count} potential game rows with selector: {selector}")

                    for i in range(count):
                        row = rows.nth(i)
                        game_data = await self._extract_game_from_row(row)
                        if game_data:
                            games.append(game_data)
                            print(
                                f"   📝 Game: {game_data['home_team']} vs {game_data['away_team']} ({game_data['home_score']}-{game_data['away_score']})"
                            )

                    if games:
                        break

            if not games:
                # Try to extract from any visible text content
                content = await page.evaluate("document.body.innerText")
                print("🔍 Attempting to extract games from page text...")
                # Add pattern matching here if needed

        except Exception as e:
            print(f"⚠️ Error extracting games: {e}")

        return games

    async def _extract_game_from_row(self, row):
        """Extract game data from a single row"""
        try:
            text = await row.text_content()
            if not text or len(text.strip()) < 10:
                return None

            # Basic extraction - this would need to be customized based on actual row structure
            parts = text.strip().split()

            # Initialize game data
            game_data = {
                "game_date": "",
                "home_team": "",
                "away_team": "",
                "home_score": "",
                "away_score": "",
                "time": "",
                "field": "",
            }

            # This is a placeholder - actual extraction logic would depend on the row format
            # You would need to parse the actual structure of the game rows

            return game_data if game_data["home_team"] and game_data["away_team"] else None

        except Exception as e:
            print(f"⚠️ Error extracting from row: {e}")
            return None

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
                "time",
                "field",
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


async def main():
    """Main function to run the scraper"""
    scraper = MLSNextScraperV2(headless=False)

    try:
        # Scrape games for September 2024 (when season starts)
        await scraper.scrape_games(match_date="2024-09-01", division="Northeast")

        # Print summary and save to CSV
        scraper.print_summary()
        scraper.save_to_csv()

    except Exception as e:
        print(f"❌ Error in main: {e}")


if __name__ == "__main__":
    asyncio.run(main())
