"""
Audit data access object for match data-integrity auditing.

Provides operations for the audit_teams scheduling table and audit_events
findings table. Used exclusively by the match-scraper-agent (service key).
"""

from datetime import UTC, datetime, timedelta

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

# Teams audited within this window are considered "up-to-date"
_AUDIT_WINDOW_DAYS = 7


class AuditDAO(BaseDAO):
    """Data Access Object for audit scheduling and findings."""

    # ── Scheduling ────────────────────────────────────────────────────────────

    def get_next_team(self, season: str, division: str, league: str) -> dict | None:
        """Return the next team to audit, or None if all teams are current.

        Selects the row with the oldest last_audited_at (NULL first = highest
        priority). Returns None when the oldest audit is still within the
        7-day window — meaning every team has been seen this week.

        Args:
            season:   Season name, e.g. "2025-2026".
            division: Division name, e.g. "Northeast".
            league:   League name, e.g. "Homegrown".

        Returns:
            Dict with team/age_group/league/division/season/last_audited_at,
            or None if all teams are up-to-date.
        """
        try:
            response = (
                self.client.table("audit_teams")
                .select("team, age_group, league, division, season, last_audited_at")
                .eq("season", season)
                .eq("division", division)
                .eq("league", league)
                .order("last_audited_at", desc=False, nulls_first=True)
                .limit(1)
                .execute()
            )
        except Exception:
            logger.exception("audit_dao.get_next_team.error")
            raise

        if not response.data:
            logger.info("audit_dao.get_next_team.no_teams", season=season)
            return None

        row = response.data[0]
        last_audited = row.get("last_audited_at")

        if last_audited is not None:
            # Parse timestamp and check if still within the audit window
            try:
                audited_dt = datetime.fromisoformat(last_audited.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                audited_dt = None

            if audited_dt is not None:
                cutoff = datetime.now(tz=UTC) - timedelta(days=_AUDIT_WINDOW_DAYS)
                if audited_dt >= cutoff:
                    logger.info(
                        "audit_dao.get_next_team.all_current",
                        season=season,
                        oldest_audit=last_audited,
                    )
                    return None

        logger.info(
            "audit_dao.get_next_team.selected",
            team=row["team"],
            age_group=row["age_group"],
            last_audited_at=last_audited,
        )
        return row

    def get_audit_teams(self, season: str, division: str, league: str) -> list[dict]:
        """Return all teams registered for auditing in a season/division/league."""
        try:
            response = (
                self.client.table("audit_teams")
                .select("*")
                .eq("season", season)
                .eq("division", division)
                .eq("league", league)
                .order("age_group")
                .order("team")
                .execute()
            )
            return response.data or []
        except Exception:
            logger.exception("audit_dao.get_audit_teams.error")
            raise

    # ── Event submission ──────────────────────────────────────────────────────

    def submit_audit_event(self, event_data: dict) -> None:
        """Record a completed audit run and update the team's scheduling state.

        Always upserts audit_teams.last_audited_at (records that an audit ran).
        Only inserts an audit_events row when findings exist.

        Args:
            event_data: Dict matching the POST /api/agent/audit/events body:
                event_id, audit_run_id, team, age_group, league,
                division, season, findings (list of dicts).
        """
        event_id = event_data["event_id"]
        team = event_data["team"]
        age_group = event_data["age_group"]
        league = event_data["league"]
        division = event_data["division"]
        season = event_data["season"]
        findings = event_data.get("findings", [])
        now_iso = datetime.now(tz=UTC).isoformat()

        audit_status = "findings" if findings else "clean"

        # 1. Upsert audit_teams scheduling state
        try:
            self.client.table("audit_teams").upsert(
                {
                    "team": team,
                    "age_group": age_group,
                    "league": league,
                    "division": division,
                    "season": season,
                    "last_audited_at": now_iso,
                    "last_audit_status": audit_status,
                    "findings_count": len(findings),
                },
                on_conflict="team,age_group,league,division,season",
            ).execute()
        except Exception:
            logger.exception(
                "audit_dao.submit_event.upsert_team_error",
                team=team,
                age_group=age_group,
            )
            raise

        # 2. Insert audit_events row only when there are findings
        if not findings:
            logger.info(
                "audit_dao.submit_event.clean",
                team=team,
                age_group=age_group,
                event_id=event_id,
            )
            return

        try:
            self.client.table("audit_events").insert(
                {
                    "event_id": event_id,
                    "audit_run_id": event_data.get("audit_run_id", event_id),
                    "team": team,
                    "age_group": age_group,
                    "league": league,
                    "division": division,
                    "season": season,
                    "findings": findings,
                    "status": "pending",
                }
            ).execute()
        except Exception:
            logger.exception(
                "audit_dao.submit_event.insert_error",
                event_id=event_id,
                team=team,
            )
            raise

        logger.info(
            "audit_dao.submit_event.done",
            event_id=event_id,
            team=team,
            age_group=age_group,
            findings=len(findings),
        )

    # ── Event processing ──────────────────────────────────────────────────────

    def get_events(
        self,
        season: str,
        status: str = "pending",
        team: str | None = None,
        age_group: str | None = None,
    ) -> list[dict]:
        """Return audit events filtered by status (and optionally team/age_group)."""
        try:
            query = (
                self.client.table("audit_events")
                .select("*")
                .eq("season", season)
                .eq("status", status)
                .order("created_at", desc=False)
            )
            if team:
                query = query.eq("team", team)
            if age_group:
                query = query.eq("age_group", age_group)

            response = query.execute()
            return response.data or []
        except Exception:
            logger.exception("audit_dao.get_events.error", season=season, status=status)
            raise

    def update_event_status(
        self,
        event_id: str,
        status: str,
        processed_at: str | None = None,
    ) -> None:
        """Update the processing status of an audit event."""
        payload: dict = {"status": status}
        if processed_at:
            payload["processed_at"] = processed_at

        try:
            self.client.table("audit_events").update(payload).eq("event_id", event_id).execute()
        except Exception:
            logger.exception(
                "audit_dao.update_event_status.error",
                event_id=event_id,
                status=status,
            )
            raise

        logger.info("audit_dao.update_event_status", event_id=event_id, status=status)

    # ── Summary ───────────────────────────────────────────────────────────────

    def get_audit_summary(self, season: str, division: str, league: str) -> dict:
        """Return audit coverage metrics for a season/division/league."""
        from datetime import date

        cutoff = (date.today() - timedelta(days=_AUDIT_WINDOW_DAYS)).isoformat()

        try:
            teams_resp = (
                self.client.table("audit_teams")
                .select("team, age_group, last_audited_at, last_audit_status, findings_count")
                .eq("season", season)
                .eq("division", division)
                .eq("league", league)
                .execute()
            )
        except Exception:
            logger.exception("audit_dao.get_audit_summary.error")
            raise

        teams = teams_resp.data or []
        total = len(teams)
        audited_this_week = sum(1 for t in teams if t.get("last_audited_at") and t["last_audited_at"][:10] >= cutoff)
        overdue = total - audited_this_week
        clean = sum(1 for t in teams if t.get("last_audit_status") == "clean")
        with_findings = sum(1 for t in teams if t.get("last_audit_status") == "findings")

        # Findings breakdown from pending events
        findings_by_type: dict[str, int] = {}
        try:
            events_resp = (
                self.client.table("audit_events")
                .select("findings")
                .eq("season", season)
                .eq("status", "pending")
                .execute()
            )
            for ev in events_resp.data or []:
                for f in ev.get("findings", []):
                    ft = f.get("finding_type", "unknown")
                    findings_by_type[ft] = findings_by_type.get(ft, 0) + 1
        except Exception:
            logger.warning("audit_dao.get_audit_summary.findings_error")

        return {
            "season": season,
            "total_teams": total,
            "audited_this_week": audited_this_week,
            "overdue_teams": overdue,
            "findings_by_type": findings_by_type,
            "teams_with_findings": with_findings,
            "clean_teams": clean,
        }
