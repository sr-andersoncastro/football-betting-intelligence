"""Data synchronization service for football data."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import (
    Competition, Season, Team, Fixture, FixtureEvent, FixtureStatistics,
    FixtureLineup, Player, Referee, TeamStatistics, Bookmaker, FixtureOdds, SyncLog
)
from backend.providers import (
    APIFootballClient, APIFootballNormalizer,
    FootballDataClient, FootballDataNormalizer,
)
from config.settings import settings

logger = logging.getLogger(__name__)


class SyncService:
    """Service for synchronizing data from external APIs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _log_sync(
        self,
        provider: str,
        operation: str,
        competition_id: Optional[int] = None,
        season: Optional[int] = None,
        status: str = "success",
        records_processed: int = 0,
        records_created: int = 0,
        records_updated: int = 0,
        error_message: Optional[str] = None,
    ) -> SyncLog:
        """Log synchronization operation."""
        sync_log = SyncLog(
            provider=provider,
            operation=operation,
            competition_id=competition_id,
            season=season,
            status=status,
            records_processed=records_processed,
            records_created=records_created,
            records_updated=records_updated,
            error_message=error_message,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        self.db.add(sync_log)
        await self.db.flush()
        return sync_log

    # Competition Sync
    async def sync_competitions(self, provider: str = "api_football") -> dict:
        """Synchronize competitions from provider."""
        started_at = datetime.utcnow()
        records_processed = records_created = records_updated = 0
        error_message = None
        status = "success"

        try:
            if provider == "api_football":
                async with APIFootballClient() as client:
                    competitions_data = await client.get_competitions()

                for comp_data in competitions_data:
                    normalized = APIFootballNormalizer.normalize_competition(comp_data)
                    if not normalized.get("id"):
                        continue

                    records_processed += 1
                    existing = await self.db.get(Competition, normalized["id"])
                    if existing:
                        for key, value in normalized.items():
                            setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                        records_updated += 1
                    else:
                        competition = Competition(**normalized)
                        self.db.add(competition)
                        records_created += 1

                    # Sync seasons for this competition
                    await self._sync_seasons_for_competition(normalized["id"], provider)

            elif provider == "football_data":
                async with FootballDataClient() as client:
                    competitions_data = await client.get_competitions()

                for comp_data in competitions_data:
                    normalized = FootballDataNormalizer.normalize_competition(comp_data)
                    if not normalized.get("id"):
                        continue

                    records_processed += 1
                    existing = await self.db.get(Competition, normalized["id"])
                    if existing:
                        for key, value in normalized.items():
                            setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                        records_updated += 1
                    else:
                        competition = Competition(**normalized)
                        self.db.add(competition)
                        records_created += 1

        except Exception as e:
            status = "failed"
            error_message = str(e)
            logger.error(f"Error syncing competitions from {provider}: {e}")

        await self._log_sync(
            provider=provider,
            operation="competitions",
            status=status,
            records_processed=records_processed,
            records_created=records_created,
            records_updated=records_updated,
            error_message=error_message,
        )

        return {
            "provider": provider,
            "operation": "competitions",
            "status": status,
            "records_processed": records_processed,
            "records_created": records_created,
            "records_updated": records_updated,
            "error": error_message,
        }

    async def _sync_seasons_for_competition(self, competition_id: int, provider: str):
        """Sync seasons for a competition."""
        try:
            if provider == "api_football":
                async with APIFootballClient() as client:
                    comp_data = await client.get_competition_by_id(competition_id)
                    if not comp_data:
                        return

                    seasons_data = comp_data.get("league", {}).get("seasons", [])
                    for season_data in seasons_data:
                        if not season_data:
                            continue
                        season_year = season_data.get("year") if isinstance(season_data, dict) else season_data
                        if not season_year:
                            continue

                        existing = await self.db.execute(
                            select(Season).where(
                                and_(Season.competition_id == competition_id, Season.year == season_year)
                            )
                        )
                        season = existing.scalar_one_or_none()
                        if not season:
                            season = Season(
                                competition_id=competition_id,
                                year=season_year,
                                is_current=season_data.get("current", False) if isinstance(season_data, dict) else False,
                            )
                            self.db.add(season)
        except Exception as e:
            logger.error(f"Error syncing seasons for competition {competition_id}: {e}")

    # Team Sync
    async def sync_teams(self, competition_id: int, season: int, provider: str = "api_football") -> dict:
        """Synchronize teams for a competition and season."""
        started_at = datetime.utcnow()
        records_processed = records_created = records_updated = 0
        error_message = None
        status = "success"

        try:
            if provider == "api_football":
                async with APIFootballClient() as client:
                    teams_data = await client.get_teams_by_league(competition_id, season)

                for team_data in teams_data:
                    normalized = APIFootballNormalizer.normalize_team(team_data)
                    if not normalized.get("id"):
                        continue

                    normalized["competition_id"] = competition_id
                    records_processed += 1
                    existing = await self.db.get(Team, normalized["id"])
                    if existing:
                        for key, value in normalized.items():
                            setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                        records_updated += 1
                    else:
                        team = Team(**normalized)
                        self.db.add(team)
                        records_created += 1

            elif provider == "football_data":
                code = self._get_competition_code(competition_id)
                if code:
                    async with FootballDataClient() as client:
                        teams_data = await client.get_teams_by_competition(code, season)

                    for team_data in teams_data:
                        normalized = FootballDataNormalizer.normalize_team(team_data)
                        if not normalized.get("id"):
                            continue

                        normalized["competition_id"] = competition_id
                        records_processed += 1
                        existing = await self.db.get(Team, normalized["id"])
                        if existing:
                            for key, value in normalized.items():
                                setattr(existing, key, value)
                            existing.updated_at = datetime.utcnow()
                            records_updated += 1
                        else:
                            team = Team(**normalized)
                            self.db.add(team)
                            records_created += 1

        except Exception as e:
            status = "failed"
            error_message = str(e)
            logger.error(f"Error syncing teams for competition {competition_id}: {e}")

        await self._log_sync(
            provider=provider,
            operation="teams",
            competition_id=competition_id,
            season=season,
            status=status,
            records_processed=records_processed,
            records_created=records_created,
            records_updated=records_updated,
            error_message=error_message,
        )

        return {
            "provider": provider,
            "operation": "teams",
            "competition_id": competition_id,
            "season": season,
            "status": status,
            "records_processed": records_processed,
            "records_created": records_created,
            "records_updated": records_updated,
            "error": error_message,
        }

    def _get_competition_code(self, competition_id: int) -> Optional[str]:
        """Map internal competition ID to football-data.org code."""
        mapping = {
            39: "PL", 140: "PD", 78: "BL1", 135: "SA",
            61: "FL1", 2: "CL", 3: "EL",
        }
        return mapping.get(competition_id)

    # Fixture Sync
    async def sync_fixtures(
        self,
        competition_id: int,
        season: int,
        days_ahead: int = 7,
        days_behind: int = 30,
        provider: str = "api_football"
    ) -> dict:
        """Synchronize fixtures for a competition."""
        started_at = datetime.utcnow()
        records_processed = records_created = records_updated = 0
        error_message = None
        status = "success"

        try:
            date_from = (datetime.utcnow() - timedelta(days=days_behind)).strftime("%Y-%m-%d")
            date_to = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

            if provider == "api_football":
                async with APIFootballClient() as client:
                    fixtures_data = await client.get_fixtures_by_date_range(
                        competition_id, season, date_from, date_to
                    )

                for fixture_data in fixtures_data:
                    normalized = APIFootballNormalizer.normalize_fixture(fixture_data)
                    if not normalized.get("id"):
                        continue

                    normalized["season_id"] = await self._get_season_id(competition_id, season)
                    if not normalized["season_id"]:
                        continue

                    records_processed += 1
                    existing = await self.db.get(Fixture, normalized["id"])
                    if existing:
                        for key, value in normalized.items():
                            setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                        records_updated += 1
                    else:
                        fixture = Fixture(**normalized)
                        self.db.add(fixture)
                        records_created += 1

                    # Sync related data
                    await self._sync_fixture_details(normalized["id"], provider)

        except Exception as e:
            status = "failed"
            error_message = str(e)
            logger.error(f"Error syncing fixtures for competition {competition_id}: {e}")

        await self._log_sync(
            provider=provider,
            operation="fixtures",
            competition_id=competition_id,
            season=season,
            status=status,
            records_processed=records_processed,
            records_created=records_created,
            records_updated=records_updated,
            error_message=error_message,
        )

        return {
            "provider": provider,
            "operation": "fixtures",
            "competition_id": competition_id,
            "season": season,
            "status": status,
            "records_processed": records_processed,
            "records_created": records_created,
            "records_updated": records_updated,
            "error": error_message,
        }

    async def _get_season_id(self, competition_id: int, season_year: int) -> Optional[int]:
        """Get season ID from competition and year."""
        result = await self.db.execute(
            select(Season.id).where(
                and_(Season.competition_id == competition_id, Season.year == season_year)
            )
        )
        return result.scalar_one_or_none()

    async def _sync_fixture_details(self, fixture_id: int, provider: str):
        """Sync events, statistics, lineups for a fixture."""
        try:
            if provider == "api_football":
                async with APIFootballClient() as client:
                    # Statistics
                    stats_data = await client.get_fixture_statistics(fixture_id)
                    if stats_data:
                        normalized_stats = APIFootballNormalizer.normalize_statistics(stats_data)
                        for stat in normalized_stats:
                            stat["fixture_id"] = fixture_id
                            self.db.add(FixtureStatistics(**stat))

                    # Events
                    events_data = await client.get_fixture_events(fixture_id)
                    if events_data:
                        normalized_events = APIFootballNormalizer.normalize_events(events_data)
                        for event in normalized_events:
                            event["fixture_id"] = fixture_id
                            self.db.add(FixtureEvent(**event))

                    # Lineups
                    lineups_data = await client.get_fixture_lineups(fixture_id)
                    if lineups_data:
                        normalized_lineups = APIFootballNormalizer.normalize_lineups(lineups_data)
                        for lineup in normalized_lineups:
                            lineup["fixture_id"] = fixture_id
                            self.db.add(FixtureLineup(**lineup))

        except Exception as e:
            logger.error(f"Error syncing fixture details for {fixture_id}: {e}")

    # Odds Sync
    async def sync_odds(self, fixture_id: int, provider: str = "api_football") -> dict:
        """Synchronize odds for a fixture."""
        started_at = datetime.utcnow()
        records_processed = records_created = records_updated = 0
        error_message = None
        status = "success"

        try:
            if provider == "api_football":
                async with APIFootballClient() as client:
                    odds_data = await client.get_odds_by_fixture(fixture_id)

                for odds_entry in odds_data:
                    bookmaker_data = odds_entry.get("bookmaker", {})
                    bookmaker_id = bookmaker_data.get("id")
                    if not bookmaker_id:
                        continue

                    # Upsert bookmaker
                    existing_bm = await self.db.get(Bookmaker, bookmaker_id)
                    if not existing_bm:
                        bm_normalized = APIFootballNormalizer.normalize_bookmaker(odds_entry)
                        bookmaker = Bookmaker(**bm_normalized)
                        self.db.add(bookmaker)

                    # Normalize odds
                    normalized_odds = APIFootballNormalizer.normalize_odds([odds_entry])
                    for odd in normalized_odds:
                        odd["fixture_id"] = fixture_id
                        odd["bookmaker_id"] = bookmaker_id
                        records_processed += 1

                        # Check if exists
                        result = await self.db.execute(
                            select(FixtureOdds).where(
                                and_(
                                    FixtureOdds.fixture_id == fixture_id,
                                    FixtureOdds.bookmaker_id == bookmaker_id,
                                    FixtureOdds.market_type == odd["market_type"],
                                    FixtureOdds.value == odd["value"],
                                )
                            )
                        )
                        existing_odd = result.scalar_one_or_none()
                        if existing_odd:
                            for key, value in odd.items():
                                setattr(existing_odd, key, value)
                            records_updated += 1
                        else:
                            self.db.add(FixtureOdds(**odd))
                            records_created += 1

        except Exception as e:
            status = "failed"
            error_message = str(e)
            logger.error(f"Error syncing odds for fixture {fixture_id}: {e}")

        await self._log_sync(
            provider=provider,
            operation="odds",
            status=status,
            records_processed=records_processed,
            records_created=records_created,
            records_updated=records_updated,
            error_message=error_message,
        )

        return {
            "provider": provider,
            "operation": "odds",
            "fixture_id": fixture_id,
            "status": status,
            "records_processed": records_processed,
            "records_created": records_created,
            "records_updated": records_updated,
            "error": error_message,
        }

    # Full Sync Pipeline
    async def full_sync(
        self,
        competition_ids: Optional[List[int]] = None,
        season: Optional[int] = None,
        days_ahead: int = 7,
        days_behind: int = 30,
        providers: Optional[List[str]] = None,
    ) -> dict:
        """Run full synchronization pipeline."""
        providers = providers or ["api_football", "football_data"]
        competition_ids = competition_ids or settings.COMPETITIONS
        season = season or datetime.utcnow().year

        results = {
            "started_at": datetime.utcnow().isoformat(),
            "competitions": [],
            "teams": [],
            "fixtures": [],
            "odds": [],
        }

        # Sync competitions
        for provider in providers:
            if provider == "football_data" and competition_ids:
                # football-data.org doesn't have Brasileirão
                comp_ids = [c for c in competition_ids if c not in [71, 72]]
            else:
                comp_ids = competition_ids

            comp_result = await self.sync_competitions(provider)
            results["competitions"].append(comp_result)

        # Sync teams and fixtures for each competition
        for comp_id in competition_ids:
            for provider in providers:
                if provider == "football_data" and comp_id in [71, 72]:
                    continue

                team_result = await self.sync_teams(comp_id, season, provider)
                results["teams"].append(team_result)

                fixture_result = await self.sync_fixtures(
                    comp_id, season, days_ahead, days_behind, provider
                )
                results["fixtures"].append(fixture_result)

        results["completed_at"] = datetime.utcnow().isoformat()
        return results