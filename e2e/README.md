# Playwright E2E Testing Framework

A professional-grade end-to-end testing framework for Missing Table using Playwright and pytest.

## Features

- **Page Object Model (POM)** - Maintainable, reusable page abstractions
- **Data-Driven Testing** - JSON-based test data for comprehensive coverage
- **Multiple Authentication Fixtures** - Pre-configured user roles (admin, team_manager, user)
- **Visual Regression Testing** - Screenshot comparison for UI consistency
- **Parallel Execution** - Run tests concurrently for faster feedback
- **Rich Reporting** - HTML reports with screenshots and videos
- **Smart Waiting** - Intelligent element waiting and error handling
- **Cross-Browser Support** - Run on Chromium, Firefox, and WebKit

## Quick Start

### Prerequisites

```bash
# Install dependencies
cd backend
uv add pytest-playwright pytest-html pillow

# Install browsers
uv run playwright install chromium
```

### Running Tests

```bash
# Run all tests (from playwright directory)
cd backend/tests/e2e/playwright
uv run pytest

# Run with visible browser
uv run pytest --headed

# Run specific test file
uv run pytest test_authentication.py

# Run tests by marker
uv run pytest -m smoke          # Quick smoke tests
uv run pytest -m critical       # Critical path tests
uv run pytest -m "auth"         # Authentication tests
uv run pytest -m "standings"    # Standings tests
uv run pytest -m "visual"       # Visual regression tests

# Run with multiple browsers
uv run pytest --browser chromium --browser firefox

# Run in parallel
uv run pytest -n auto
```

## Project Structure

```
playwright/
├── conftest.py              # All pytest fixtures
├── pytest.ini               # Pytest configuration
├── README.md                # This file
│
├── page_objects/            # Page Object Model classes
│   ├── __init__.py
│   ├── base_page.py         # Base class for all pages
│   ├── login_page.py        # Login page object
│   ├── standings_page.py    # Standings page object
│   ├── matches_page.py      # Matches page object
│   ├── admin_page.py        # Admin panel page object
│   └── navigation.py        # Navigation bar component
│
├── fixtures/                # Custom test fixtures
│   ├── __init__.py
│   └── visual_regression.py # Visual testing utilities
│
├── test_data/               # Test data JSON files
│   ├── login_scenarios.json
│   ├── filter_scenarios.json
│   └── user_journeys.json
│
├── plugins/                 # Custom pytest plugins
│
├── screenshots/             # Visual regression baselines
│   ├── baseline/
│   └── diff/
│
├── videos/                  # Test execution videos
│
└── test-results/            # Test output directory
    ├── report.html          # HTML test report
    └── pytest.log           # Test execution log
```

## Page Object Model

### Creating a New Page Object

```python
from page_objects.base_page import BasePage

class MyPage(BasePage):
    """Page Object for My Feature."""
    
    URL_PATH = "/my-feature"
    PAGE_TITLE = "My Feature"
    
    # Selectors
    SUBMIT_BUTTON = "button[type='submit']"
    INPUT_FIELD = "#my-input"
    
    def __init__(self, page, base_url):
        super().__init__(page, base_url)
    
    def do_something(self, value: str):
        """Perform an action on the page."""
        self.fill(self.INPUT_FIELD, value)
        self.click(self.SUBMIT_BUTTON)
        self.wait_for_network_idle()
```

### Using Page Objects in Tests

```python
def test_my_feature(page, base_url):
    """Test my feature works correctly."""
    my_page = MyPage(page, base_url)
    
    # Navigate to page
    my_page.navigate()
    
    # Perform actions
    my_page.do_something("test value")
    
    # Assert results
    assert my_page.is_visible(".success-message")
```

## Fixtures

### Authentication Fixtures

```python
# Pre-configured user fixtures
def test_as_regular_user(authenticated_page, standings_page):
    """Test with logged-in regular user."""
    standings_page.navigate()
    # User is already authenticated

def test_as_admin(admin_authenticated_page, admin_page):
    """Test with admin user."""
    admin_page.navigate()
    # Admin is authenticated

# Fast admin page (uses stored state, skips login)
def test_admin_fast(admin_page_fast):
    """Admin page without re-login."""
    admin_page_fast.goto("/admin")
```

### Page Object Fixtures

```python
def test_login(login_page):
    """login_page fixture is automatically injected."""
    login_page.navigate()
    login_page.login("user@example.com", "password")

def test_standings(standings_page):
    """standings_page fixture is automatically injected."""
    standings_page.navigate()
    standings = standings_page.get_standings()
```

### Test Data Fixtures

```python
def test_with_sample_data(sample_team_data, sample_match_data):
    """Get generated test data."""
    print(sample_team_data["name"])  # Random team name
```

## Data-Driven Testing

### Using Parametrize

```python
@pytest.mark.parametrize("email,password,expected", [
    ("valid@example.com", "password123", "success"),
    ("invalid", "password", "error"),
    ("", "password", "validation_error"),
])
def test_login_scenarios(login_page, email, password, expected):
    """Run same test with different data."""
    login_page.navigate()
    login_page.login(email, password)
    
    if expected == "success":
        assert login_page.is_login_successful()
    elif expected == "error":
        assert login_page.has_error_message()
```

### Using JSON Test Data

```python
# Load from test_data/login_scenarios.json
def test_from_json(login_page, login_test_data):
    """Execute tests from JSON file."""
    for scenario in login_test_data:
        login_page.navigate()
        login_page.login(scenario["email"], scenario["password"])
        # Assert based on expected_result
```

## Visual Regression Testing

### Basic Usage

```python
def test_homepage_visual(standings_page, visual_regression):
    """Compare homepage against baseline screenshot."""
    standings_page.navigate()
    
    # Compare full page
    assert visual_regression.compare("homepage")
    
    # Compare specific element
    assert visual_regression.compare(
        "standings_table",
        element=".standings-table"
    )
```

### Managing Baselines

```bash
# First run creates baselines automatically
uv run pytest test_visual.py

# Update baselines after intentional UI changes
# Set update_baseline=True in test or delete old baseline
```

## Markers

Run tests by category using markers:

| Marker | Description |
|--------|-------------|
| `smoke` | Quick critical path tests |
| `critical` | Must-pass tests for deployment |
| `auth` | Authentication tests |
| `standings` | Standings feature tests |
| `matches` | Matches feature tests |
| `admin` | Admin panel tests |
| `visual` | Visual regression tests |
| `data_driven` | Parametrized data tests |
| `slow` | Tests > 5 seconds |
| `security` | Security-focused tests |
| `a11y` | Accessibility tests |

## Configuration

### Environment Variables

```bash
# Frontend URL (default: http://localhost:8080)
export E2E_BASE_URL=http://localhost:8080

# Backend API URL (default: http://localhost:8000)
export E2E_API_URL=http://localhost:8000

# Test user credentials
export E2E_ADMIN_EMAIL=admin@example.com
export E2E_ADMIN_PASSWORD=AdminPassword123!
export E2E_MANAGER_EMAIL=manager@example.com
export E2E_USER_EMAIL=user@example.com
```

### pytest.ini Options

Key configurations in `pytest.ini`:

- `--headed`: Show browser during tests
- `--slowmo 100`: Slow down actions (debugging)
- `--video retain-on-failure`: Record videos
- `--screenshot only-on-failure`: Capture on failure
- `--browser chromium/firefox/webkit`: Browser selection

## Best Practices

### Writing Maintainable Tests

1. **Use Page Objects**: Never put selectors in test files
2. **Single Responsibility**: Each test verifies one thing
3. **Descriptive Names**: `test_admin_can_create_team_with_valid_data`
4. **Comments**: Explain business logic being tested
5. **Arrange-Act-Assert**: Clear test structure

### Selector Strategy

1. **Prefer data-testid**: `[data-testid='submit-button']`
2. **Use accessible selectors**: `button[role='submit']`
3. **Avoid brittle selectors**: No `.css-xyz123` class names
4. **Multiple fallbacks**: `"button#submit, [data-testid='submit']"`

### Handling Flaky Tests

1. **Smart waiting**: Use `wait_for_load()` not `sleep()`
2. **Retry API calls**: Wait for network idle
3. **Isolate tests**: No shared state between tests
4. **Stable selectors**: Use IDs and data attributes

## Troubleshooting

### Common Issues

**Browser not installed:**
```bash
uv run playwright install chromium
```

**Tests timing out:**
- Increase timeout in page object
- Check if services are running
- Look for network issues

**Screenshots not matching:**
- Different font rendering
- Different screen DPI
- Increase threshold in visual_regression

**Authentication failures:**
- Check user exists in database
- Verify environment variables
- Check token expiration

### Debug Mode

```bash
# Run with debugger
uv run pytest --headed --slowmo 500 -x

# Pause on error
PWDEBUG=1 uv run pytest test_file.py::test_name
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run E2E Tests
  run: |
    cd backend/tests/e2e/playwright
    uv run pytest --browser chromium --headed=false
    
- name: Upload Test Results
  uses: actions/upload-artifact@v3
  if: always()
  with:
    name: test-results
    path: backend/tests/e2e/playwright/test-results/
```

## Contributing

1. Follow the Page Object Model pattern
2. Add tests for new features
3. Update test data files as needed
4. Run full test suite before PR
5. Keep baselines up to date

## License

Part of the Missing Table project.
