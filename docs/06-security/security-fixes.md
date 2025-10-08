# Security Fixes and Recommendations

This document tracks security warnings from Supabase and their resolution status.

## ✅ Resolved Issues

### 1. RLS Disabled in Public Tables (ERROR - RESOLVED)
**Status:** ✅ Fixed in migration `011_enable_rls_security.sql`

**Issue:** 12 tables had Row Level Security disabled, exposing data to unauthorized access.

**Resolution:**
- Enabled RLS on all public tables
- Created helper functions with SECURITY DEFINER to avoid recursion
- Implemented role-based policies (anon, authenticated, admin, team_manager)
- Public read access for league data, protected write operations

**Tables Fixed:**
- Core: teams, games, seasons, age_groups, game_types, divisions
- Mappings: team_mappings, team_game_types
- Users: user_profiles, invitations, team_manager_assignments
- Services: service_accounts

---

### 2. Function Search Path Mutable (WARN - RESOLVED)
**Status:** ✅ Fixed in migration `012_fix_function_search_paths.sql`

**Issue:** 10 functions lacked explicit `search_path`, vulnerable to schema injection attacks.

**Resolution:**
- Added `SET search_path = public, pg_temp` to all functions
- Prevents attackers from creating malicious schemas to override function behavior
- Critical for RLS security functions used in policies

**Functions Fixed:**
- RLS Functions: `is_admin()`, `is_team_manager()`, `manages_team()`
- User Management: `handle_new_user()`, `get_user_role()`, `user_has_role()`, `promote_to_admin()`
- Utilities: `update_updated_at_column()`, `generate_invite_code()`, `expire_old_invitations()`

---

## ⚠️ Pending Configuration Changes

### 3. Leaked Password Protection Disabled (WARN)
**Status:** ⚠️ Requires Supabase Dashboard Configuration

**Issue:** Users can set passwords that have been compromised in data breaches.

**Recommendation:** **Enable before production launch**

**How to Fix:**
1. Go to Supabase Dashboard → Your Project
2. Navigate to **Authentication** → **Policies**
3. Find **Password Strength** section
4. Enable **"Leaked Password Protection"**
5. This checks passwords against the HaveIBeenPwned.org database

**Impact:**
- ✅ Prevents users from using known compromised passwords
- ✅ No code changes required
- ✅ Improves account security without affecting UX significantly

**Risk if not fixed:** Users may set passwords that are already known to attackers from previous breaches.

---

### 4. Insufficient MFA Options (WARN)
**Status:** ⚠️ Optional - Depends on Security Requirements

**Issue:** Limited multi-factor authentication options may weaken account security.

**Recommendation:** **Consider enabling for production, especially for admin/team manager accounts**

**How to Fix:**
1. Go to Supabase Dashboard → Your Project
2. Navigate to **Authentication** → **Providers**
3. Enable additional MFA methods:
   - **TOTP (Time-based OTP)** - Apps like Google Authenticator, Authy
   - **Phone (SMS)** - Requires SMS provider setup
   - **WebAuthn** - Hardware keys, biometrics

**Recommended Approach:**
- Enable **TOTP** (most common, no extra costs)
- Make MFA **optional** for regular users (team-fan, team-player)
- Consider making MFA **required** for privileged roles (admin, team-manager)

**Implementation Notes:**
- Frontend changes needed to support MFA enrollment
- Update authentication flows in `frontend/src/components/LoginForm.vue`
- Add MFA management UI in user profile settings

**Risk if not fixed:** Accounts vulnerable to credential theft attacks. Lower risk for public-facing league data, higher risk for admin accounts.

---

### 5. Vulnerable Postgres Version (WARN)
**Status:** ⚠️ Requires Testing Before Production

**Issue:** Current Postgres version `supabase-postgres-17.4.1.048` has security patches available.

**Recommendation:** **Upgrade after testing in development environment**

**How to Fix:**

#### Development Environment
1. Go to Supabase Dashboard → Development Project
2. Navigate to **Database** → **Settings**
3. Find **Postgres Version** section
4. Click **"Upgrade Postgres"**
5. Follow the upgrade wizard
6. Wait for upgrade to complete (typically 5-10 minutes)

#### Testing Checklist
After upgrading dev, test:
- [ ] User authentication (login, signup, logout)
- [ ] RLS policies (can users only see/edit what they should?)
- [ ] Game data CRUD operations
- [ ] Team standings calculations
- [ ] Invitation system
- [ ] Admin functions

#### Production Environment
1. Schedule during **low-traffic period**
2. Create fresh backup: `./scripts/db_tools.sh backup prod`
3. Announce brief maintenance window to users
4. Perform upgrade in Supabase Dashboard → Production Project
5. Monitor application logs for errors
6. Verify critical functionality

**Rollback Plan:**
- Supabase typically allows point-in-time recovery
- Keep recent backup available
- Document any schema changes made between backup and upgrade

**Risk if not fixed:** Potential security vulnerabilities in Postgres. However, Supabase typically includes critical security patches automatically. Review release notes for specific CVEs addressed.

---

## Summary: Pre-Launch Checklist

### Critical (Must Fix)
- [x] Enable RLS on all tables
- [x] Fix function search paths

### Important (Strongly Recommended)
- [ ] Enable leaked password protection (5 min, no code changes)
- [ ] Upgrade Postgres version (test in dev first)

### Optional (Consider Based on Requirements)
- [ ] Enable additional MFA options (requires frontend changes)

---

## Monitoring and Maintenance

### Regular Security Checks
1. **Weekly:** Check Supabase Dashboard → Database → Linter for new warnings
2. **Monthly:** Review user roles and permissions
3. **Quarterly:** Audit RLS policies for effectiveness

### Security Best Practices
- Keep dependencies updated (`npm audit`, `pip-audit`)
- Monitor failed authentication attempts
- Review admin action logs
- Regular database backups (automated via `db_tools.sh`)

### Resources
- [Supabase Security Best Practices](https://supabase.com/docs/guides/platform/going-into-prod)
- [Database Linter Documentation](https://supabase.com/docs/guides/database/database-linter)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)

---

## Contact and Support

For security concerns or questions:
1. Review Supabase documentation
2. Check project's GitHub issues
3. Consult with team security lead

**Last Updated:** 2025-09-30
**Next Review:** Before production launch
