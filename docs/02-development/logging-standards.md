# Logging Standards

This document defines logging standards for the Missing Table application, covering both frontend and backend. These standards ensure consistent, searchable logs in Grafana Loki.

## Overview

The application uses a **distributed tracing** approach:
- **Session ID** (`mt-sess-*`): Persists for the browser session, correlates all actions by a single user session
- **Request ID** (`mt-req-*`): Unique per API call, correlates frontend request with backend processing

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Browser Session                                                          │
│ session_id: mt-sess-a1b2c3d4                                            │
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│  │ API Call 1  │    │ API Call 2  │    │ API Call 3  │                 │
│  │ req: mt-req-│    │ req: mt-req-│    │ req: mt-req-│                 │
│  │ x1y2z3      │    │ a4b5c6      │    │ d7e8f9      │                 │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                 │
│         │                  │                  │                         │
└─────────┼──────────────────┼──────────────────┼─────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Backend API                                                              │
│ Each request logged with session_id + request_id                        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Trace ID Formats

| ID Type | Format | Example | Persistence |
|---------|--------|---------|-------------|
| Session ID | `mt-sess-{8 hex}` | `mt-sess-2c83833c` | Browser session (sessionStorage) |
| Request ID | `mt-req-{8 hex}` | `mt-req-54010322` | Single request |

Short 8-character hex IDs (4.3 billion combinations) - easy to copy/paste for Grafana queries.

## Frontend Logging

### Tools
- **Grafana Faro**: Automatic error tracking, Web Vitals, session management
- **Custom trace context**: Session and request ID generation

### Log Levels
| Level | When to Use | Example |
|-------|-------------|---------|
| `error` | Unrecoverable failures | API call failed after retries |
| `warn` | Recoverable issues | Token refresh needed |
| `info` | Key user actions | Login, logout, form submission |
| `debug` | Development only | State changes, computed values |

### Required Context
Every log should include:
- `session_id`: From trace context
- `request_id`: For API calls
- `user_id`: When authenticated (via Faro user context)

### Example Usage
```javascript
import { getSessionId, generateRequestId } from '@/utils/traceContext';
import { getFaro } from '@/faro';

// For API calls
const requestId = generateRequestId();
const response = await fetch(url, {
  headers: {
    'X-Session-ID': getSessionId(),
    'X-Request-ID': requestId,
  }
});

// Manual logging via Faro
const faro = getFaro();
if (faro) {
  faro.api.pushLog(['User clicked submit'], {
    context: {
      session_id: getSessionId(),
      action: 'form_submit',
      form_name: 'login'
    }
  });
}
```

### HTTP Headers
Frontend sends these headers with every API request:
- `X-Session-ID`: Session trace ID
- `X-Request-ID`: Per-request trace ID

## Backend Logging

### Tools
- **structlog**: Structured JSON logging
- **Trace middleware**: Extracts and binds trace IDs from headers

### Log Levels
| Level | When to Use | Example |
|-------|-------------|---------|
| `ERROR` | Failures requiring attention | Database error, auth failure |
| `WARNING` | Potential issues | Deprecated endpoint used |
| `INFO` | Request lifecycle, key events | Request start/end, user actions |
| `DEBUG` | Detailed debugging | Query parameters, internal state |

### Required Context
Every log automatically includes (via middleware):
- `session_id`: From `X-Session-ID` header
- `request_id`: From `X-Request-ID` header (or generated)
- `user_id`: When authenticated
- `service`: Service name (e.g., "backend")
- `timestamp`: ISO format
- `filename`, `lineno`: Source location

### Error Logging Best Practices

**Bad** - loses context and stack trace:
```python
logger.error(f"Error: {e}")
logger.error(f"Failed to create match: {str(e)}")
```

**Good** - structured with full context:
```python
logger.error(
    "match_creation_failed",
    error_type=type(e).__name__,
    error_message=str(e),
    match_data={"home_team": home_team_id, "away_team": away_team_id},
    exc_info=True  # Includes full stack trace
)
```

### Event Naming Convention
Use snake_case event names that describe what happened:
- `request_started`, `request_completed`
- `user_login_success`, `user_login_failed`
- `match_created`, `match_creation_failed`
- `database_query_slow`, `database_connection_error`

### Example Usage
```python
from logging_config import get_logger

logger = get_logger(__name__)

# Info level - key events
logger.info("match_created", match_id=123, home_team="FC Academy", away_team="City United")

# Warning - recoverable issues
logger.warning("token_refresh_required", user_id=user_id, token_age_seconds=3500)

# Error - with full context
try:
    result = dao.create_match(data)
except Exception as e:
    logger.error(
        "match_creation_failed",
        error_type=type(e).__name__,
        error_message=str(e),
        match_data=data,
        exc_info=True
    )
    raise
```

## Grafana Loki Queries

### Find all logs for a session
```logql
{app="missing-table"} |= "mt-sess-a1b2c3d4"
```

### Find all logs for a specific request
```logql
{app="missing-table"} |= "mt-req-x1y2z3"
```

### Find errors with context
```logql
{app="missing-table"} | json | level="error"
```

### Trace a user's journey
```logql
{app="missing-table"} | json | session_id="mt-sess-a1b2c3d4" | line_format "{{.timestamp}} [{{.level}}] {{.event}}"
```

### Find slow requests
```logql
{app="missing-table"} | json | duration_ms > 1000
```

## File Locations

| Component | File | Purpose |
|-----------|------|---------|
| Frontend trace context | `frontend/src/utils/traceContext.js` | Generate session/request IDs |
| Frontend Faro | `frontend/src/faro.js` | Observability SDK |
| Backend logging config | `backend/logging_config.py` | structlog setup |
| Backend trace middleware | `backend/middleware/trace_middleware.py` | Extract trace headers |

## Checklist for New Code

### Frontend
- [ ] Include session_id in Faro logs
- [ ] Generate request_id for API calls
- [ ] Pass trace headers to backend
- [ ] Use appropriate log level

### Backend
- [ ] Use structlog logger (not print or logging directly)
- [ ] Use snake_case event names
- [ ] Include relevant context as kwargs
- [ ] For errors: include `error_type`, `error_message`, `exc_info=True`
- [ ] Don't log sensitive data (passwords, tokens, PII)

---

*Last Updated: 2024-12-14*
