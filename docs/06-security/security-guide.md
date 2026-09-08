# Security Implementation Guide

This document describes the security measures implemented in the Sports League Management application.

## Overview

The application implements multiple layers of security:
1. **Authentication**: JWT-based authentication via Supabase
2. **Authorization**: Role-based access control (RBAC)
3. **Rate Limiting**: Protection against abuse and DDoS
4. **CSRF Protection**: Prevention of cross-site request forgery
5. **Secret Management**: Environment-based configuration

## 1. Environment Configuration

### Required Environment Variables

Create a `.env` file in the backend directory with the following variables:

```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_key
SUPABASE_JWT_SECRET=your_supabase_jwt_secret

# Security Configuration
CSRF_SECRET_KEY=generate_a_random_32_char_string
ENVIRONMENT=development  # or 'production'

# Optional: Redis, so one rate limit holds across all backend pods.
# Set it or do not — there is no separate on/off flag; an unset or
# unreachable Redis falls back to per-pod in-memory counting.
REDIS_URL=redis://localhost:6379
```

### Generating Secure Secrets

Generate secure random strings for secrets:

```bash
# Generate CSRF secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# For Supabase secrets, use the Supabase dashboard or CLI
npx supabase status
```

## 2. Rate Limiting

**Credential endpoints only.** Everything else is unlimited, on purpose.

| Endpoint | Limit |
|---|---|
| `POST /api/auth/login` | 5 per minute |
| `POST /api/auth/signup` | 3 per hour |
| `POST /api/auth/forgot-password` | 3 per hour |
| `POST /api/auth/reset-password` | 3 per hour |

This section used to describe public (100/min), authenticated (30/min) and
admin (100/min) tiers as well. None of them were ever in effect — the
middleware and every decorator were commented out — so the document
described a stricter world than the one that existed, which is worse than
saying nothing (SB-640). It now lists what the code enforces and nothing
else.

### Why there are no global limits

`SlowAPIMiddleware` exists to apply blanket `default_limits` to every
request. The old configuration set 200/hour and 50/minute, which the product
itself breaches: the LIVE tab polls while a match is being scored, and
ingest posts fixtures in bulk. Enabling it would have read as an outage.
Limits are applied per route with `@rate_limit(...)`, which needs no
middleware.

### Why the key is the forwarded IP

Behind the ingress every request arrives from one address. Keying on the
socket peer (slowapi's default `get_remote_address`) would put every user
into a single bucket, so five failed logins anywhere would lock out
everyone. `rate_limiter.client_key` reads `X-Forwarded-For` first, matching
`get_client_ip` in `app.py`. Both must stay in step.

### Redis

Set `REDIS_URL` and one limit holds across every backend pod. Without it
each pod counts on its own, so the effective limit is (pods x limit) — still
a limit, just a looser one. Reachability is checked once at import; an
unreachable Redis falls back to in-memory with a warning rather than failing
every login.

### Adding a limit

```python
@app.post("/api/endpoint")
@rate_limit("10 per minute")
async def endpoint(request: Request):  # the Request parameter is required
    pass
```

Anything added to `RATE_LIMITS` must also be applied to a route, or it is
decoration again. `tests/unit/test_rate_limiting.py` asserts the auth routes
carry one.

## 2a. Password Policy

Set wherever a password is chosen — signup and reset — and never at login,
so an existing weak password can still authenticate long enough to be
rotated.

- Minimum 12 characters, maximum 72 bytes (bcrypt truncates past that, so
  longer is not stronger, and hashing an unbounded string on a public
  endpoint is a free CPU sink).
- Rejects common bases after stripping decorative digits, so `soccer123!`
  fails on `soccer`.
- Rejects a password containing the account's own username.

No composition rules and no expiry, following NIST SP 800-63B: forcing a
symbol turns `password` into `Password1!` and buys nothing. The list lives
in `backend/constants/passwords.py`.

Reset previously accepted six characters, which made it the way around
whatever signup asked for.

## 3. CSRF Protection

### How It Works

1. Server generates a CSRF token and sets it as an HTTP-only cookie
2. Frontend fetches the token and includes it in headers for state-changing requests
3. Server validates the token on POST, PUT, DELETE, and PATCH requests

### Frontend Integration

The frontend automatically handles CSRF tokens:

```javascript
// Tokens are automatically included in API requests
const response = await authStore.apiRequest('/api/endpoint', {
  method: 'POST',
  body: JSON.stringify(data)
});
```

### Exempt Endpoints

The following endpoints are exempt from CSRF protection:
- `/api/auth/login`
- `/api/auth/signup`
- `/api/auth/refresh`
- Documentation endpoints (`/docs`, `/redoc`)

## 4. Authentication & Authorization

### User Roles

The application supports four user roles:
- **admin**: Full system access
- **team-manager**: Can manage their assigned team
- **team-player**: Can update their own profile
- **team-fan**: Read-only access (default)

### Row Level Security (RLS)

Database-level security is enforced via Supabase RLS policies:
- Users can only view their own profile
- Team managers can only edit their team's data
- Admins have full access
- Public data (teams, games) is readable by all

## 5. Security Best Practices

### Development

1. **Never commit secrets**: Use `.env` files and add them to `.gitignore`
2. **Use HTTPS**: Always use HTTPS in production
3. **Keep dependencies updated**: Regularly update packages for security patches
4. **Input validation**: Validate all user inputs using Pydantic models

### Deployment

1. **Environment separation**: Use different secrets for dev/staging/production
2. **Monitoring**: Set up logging and monitoring for security events
3. **Backup**: Regular database backups with encryption
4. **Access control**: Limit database and server access

### Security Headers

Consider adding additional security headers in production:

```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from secure import SecureHeaders

# Only allow specific hosts
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["example.com"])

# Add security headers
secure_headers = SecureHeaders()
```

## 6. Incident Response

### Suspected Security Breach

1. Immediately revoke all JWT secrets
2. Force all users to re-authenticate
3. Review access logs for suspicious activity
4. Update all secrets and API keys
5. Notify affected users if required

### Regular Security Audits

1. Review rate limiting effectiveness
2. Check for unusual access patterns
3. Update dependencies for security patches
4. Test authentication and authorization flows
5. Verify CSRF protection is working

## 7. Testing Security

### Manual Testing

1. Test rate limits:
```bash
# Should be rate limited after 5 attempts
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}'
done
```

2. Test CSRF protection:
```bash
# Should fail without CSRF token
curl -X POST http://localhost:8000/api/teams \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"name":"Test Team"}'
```

### Automated Security Scanning

Consider using tools like:
- **OWASP ZAP**: Web application security scanner
- **Bandit**: Python security linter
- **npm audit**: JavaScript dependency scanner

## Support

For security concerns or questions, please contact the development team or create a private security issue in the repository.
