#!/usr/bin/env python3
"""
Login uptime test using headless playwright to verify authentication flow.
Tests the complete login process from frontend to backend authentication.
"""

import asyncio
import sys
from playwright.async_api import async_playwright
from datetime import datetime

# Test credentials
TEST_EMAIL = "uptime_test@example.com"
TEST_PASSWORD = "Changeme!"
FRONTEND_URL = "http://localhost:8080"
TIMEOUT = 30000  # 30 seconds

class LoginUptimeTest:
    def __init__(self):
        self.browser = None
        self.page = None
        self.results = []

    async def setup_browser(self):
        """Setup headless browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        self.page = await self.browser.new_page()
        # Set viewport
        await self.page.set_viewport_size({"width": 1280, "height": 720})
        
    async def cleanup(self):
        """Cleanup browser resources."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def log_step(self, step: str, success: bool, details: str = ""):
        """Log test step result."""
        status = "✅" if success else "❌"
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = f"{status} [{timestamp}] {step}"
        if details:
            message += f" - {details}"
        print(message)
        
        self.results.append({
            'step': step,
            'success': success,
            'details': details,
            'timestamp': timestamp
        })

    async def test_frontend_loads(self):
        """Test that frontend loads successfully."""
        try:
            await self.page.goto(FRONTEND_URL, timeout=TIMEOUT)
            await self.page.wait_for_load_state('networkidle', timeout=TIMEOUT)
            
            # Wait for Vue app to initialize
            await self.page.wait_for_selector('#app', timeout=TIMEOUT)
            
            # Wait a bit more for Vue components to render
            await self.page.wait_for_timeout(3000)
            
            title = await self.page.title()
            await self.log_step("Frontend loads", True, f"Title: {title}")
            return True
        except Exception as e:
            await self.log_step("Frontend loads", False, str(e))
            return False

    async def test_login_form_exists(self):
        """Test that login form elements exist or can be accessed."""
        try:
            # First, look for direct login form elements
            email_field = None
            password_field = None
            login_button = None
            
            # Try multiple selectors for email field
            for selector in ['input[type="email"]', 'input[name="email"]', '#email', '[placeholder*="email" i]', 'input[v-model*="email"]']:
                try:
                    email_field = await self.page.wait_for_selector(selector, timeout=2000)
                    if email_field:
                        break
                except:
                    continue
                    
            # Try multiple selectors for password field
            for selector in ['input[type="password"]', 'input[name="password"]', '#password', '[placeholder*="password" i]', 'input[v-model*="password"]']:
                try:
                    password_field = await self.page.wait_for_selector(selector, timeout=2000)
                    if password_field:
                        break
                except:
                    continue
                    
            # Try multiple selectors for login button
            for selector in ['button[type="submit"]', 'input[type="submit"]', 'button:has-text("login")', 'button:has-text("sign in")', '.login-button']:
                try:
                    login_button = await self.page.wait_for_selector(selector, timeout=2000)
                    if login_button:
                        break
                except:
                    continue

            if email_field and password_field and login_button:
                await self.log_step("Login form exists", True, "All form elements found")
                return True
            
            # If direct form not found, look for login navigation link
            login_nav_selectors = [
                'a:has-text("login")', 
                'a:has-text("sign in")',
                'button:has-text("login")',
                'button:has-text("sign in")',
                '.login-nav',
                '[data-testid="login"]',
                '.nav-login'
            ]
            
            for selector in login_nav_selectors:
                try:
                    login_nav = await self.page.wait_for_selector(selector, timeout=2000)
                    if login_nav:
                        await self.log_step("Login navigation found", True, f"Found: {selector}")
                        # Click the login nav to open login form
                        await login_nav.click()
                        await self.page.wait_for_timeout(2000)
                        
                        # Now try to find form elements again
                        for selector in ['input[type="email"]', 'input[name="email"]', '#email', '[placeholder*="email" i]']:
                            try:
                                email_field = await self.page.wait_for_selector(selector, timeout=5000)
                                if email_field:
                                    break
                            except:
                                continue
                                
                        if email_field:
                            await self.log_step("Login form exists", True, "Form found after navigation")
                            return True
                        break
                except:
                    continue
                    
            # If still not found, take a screenshot for debugging
            try:
                page_content = await self.page.content()
                if len(page_content) > 1000:  # Basic check that page loaded
                    await self.log_step("Login form exists", False, "Form not found but page loaded")
                else:
                    await self.log_step("Login form exists", False, "Page may not have loaded properly")
            except:
                await self.log_step("Login form exists", False, "Could not analyze page")
                
            return False
                
        except Exception as e:
            await self.log_step("Login form exists", False, str(e))
            return False

    async def test_login_process(self):
        """Test the complete login process."""
        try:
            # Find and fill email field
            email_field = None
            for selector in ['input[type="email"]', 'input[name="email"]', '#email', '[placeholder*="email" i]']:
                try:
                    email_field = await self.page.wait_for_selector(selector, timeout=5000)
                    if email_field:
                        break
                except:
                    continue
            
            if not email_field:
                await self.log_step("Login process", False, "Could not find email field")
                return False
                
            await email_field.fill(TEST_EMAIL)
            await self.log_step("Fill email", True, TEST_EMAIL)

            # Find and fill password field
            password_field = None
            for selector in ['input[type="password"]', 'input[name="password"]', '#password', '[placeholder*="password" i]']:
                try:
                    password_field = await self.page.wait_for_selector(selector, timeout=5000)
                    if password_field:
                        break
                except:
                    continue
                    
            if not password_field:
                await self.log_step("Login process", False, "Could not find password field")
                return False
                
            await password_field.fill(TEST_PASSWORD)
            await self.log_step("Fill password", True, "Password entered")

            # Find and click login button
            login_button = None
            for selector in ['button[type="submit"]', 'input[type="submit"]', 'button:has-text("login")', 'button:has-text("sign in")', '.login-button']:
                try:
                    login_button = await self.page.wait_for_selector(selector, timeout=5000)
                    if login_button:
                        break
                except:
                    continue
                    
            if not login_button:
                await self.log_step("Login process", False, "Could not find login button")
                return False

            # Click login and wait for navigation/response
            async with self.page.expect_response(lambda response: True, timeout=TIMEOUT) as response_info:
                await login_button.click()
                await self.log_step("Click login button", True, "Login submitted")

            # Wait a moment for the login to process
            await self.page.wait_for_timeout(3000)

            # Check for successful login indicators
            success_indicators = [
                'text=logout',
                'text=profile',
                'text=dashboard',
                'text=welcome',
                '.user-menu',
                '.authenticated',
                '[data-testid="user-menu"]'
            ]

            login_successful = False
            for indicator in success_indicators:
                try:
                    element = await self.page.wait_for_selector(indicator, timeout=2000)
                    if element:
                        await self.log_step("Login success indicator", True, f"Found: {indicator}")
                        login_successful = True
                        break
                except:
                    continue

            # Check for error messages
            error_indicators = [
                'text=invalid',
                'text=error',
                'text=failed',
                '.error',
                '.alert-error',
                '[role="alert"]'
            ]

            error_found = False
            error_message = ""
            for indicator in error_indicators:
                try:
                    element = await self.page.wait_for_selector(indicator, timeout=2000)
                    if element:
                        error_message = await element.text_content()
                        await self.log_step("Login error detected", True, f"Error: {error_message}")
                        error_found = True
                        break
                except:
                    continue

            if login_successful:
                await self.log_step("Login process", True, "Login completed successfully")
                return True
            elif error_found:
                await self.log_step("Login process", False, f"Login failed: {error_message}")
                return False
            else:
                # Check URL change as fallback indicator
                current_url = self.page.url
                if current_url != FRONTEND_URL and current_url != f"{FRONTEND_URL}/":
                    await self.log_step("Login process", True, f"URL changed to: {current_url}")
                    return True
                else:
                    await self.log_step("Login process", False, "No clear success/error indicators found")
                    return False

        except Exception as e:
            await self.log_step("Login process", False, str(e))
            return False

    async def run_tests(self):
        """Run all login tests."""
        print("🔐 Login Uptime Test")
        print("=" * 40)
        print(f"Frontend URL: {FRONTEND_URL}")
        print(f"Test Email: {TEST_EMAIL}")
        print(f"Started at: {datetime.now()}")
        print()

        try:
            await self.setup_browser()

            # Run tests in sequence
            tests = [
                self.test_frontend_loads,
                self.test_login_form_exists,
                self.test_login_process
            ]

            all_passed = True
            for test in tests:
                result = await test()
                if not result:
                    all_passed = False

            print("\n📊 Test Summary")
            print("=" * 40)
            
            passed = sum(1 for r in self.results if r['success'])
            total = len(self.results)
            
            print(f"Results: {passed}/{total} tests passed")
            
            if all_passed:
                print("🎉 All login tests passed!")
                return True
            else:
                print("❌ Some login tests failed!")
                return False

        except Exception as e:
            print(f"❌ Test setup failed: {e}")
            return False
        finally:
            await self.cleanup()

async def main():
    """Main function to run login uptime tests."""
    test = LoginUptimeTest()
    success = await test.run_tests()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())