"""football-data.org provider for football data."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel

from config.settings import settings

logger = logging.getLogger(__name__)


class FootballDataResponse(BaseModel):
    """Standard football-data.org response structure."""
    filters: Dict[str, Any]
    resultSet: Dict[str, Any]
    competition: Optional[Dict[str, Any]] = None
    matches: Optional[List[Dict[str, Any]]] = None
    teams: Optional[List[Dict[str, Any]]] = None
    standings: Optional[List[Dict[str, Any]]] = None
    scorers: Optional[List[Dict[str, Any]]] = None


class FootballDataClient:
    """Client for football-data.org API."""

    # Competition codes mapping
    COMPETITION_CODES = {
        39: "PL",      # Premier League
        140: "PD",     # La Liga
        78: "BL1",     # Bundesliga
        135: "SA",     # Serie A
        61: "FL1",     # Ligue 1
        2: "CL",       # Champions League
        3: "EL",       # Europa League
        # Note: Brasileirão not available in free tier
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.FOOTBALL_DATA_KEY
        self.base_url = settings.FOOTBALL_DATA_BASE_URL
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "X-Auth-Token": self.api_key,
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def _request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a request to the API."""
        if not self.client:
            raise Exception("Client not initialized. Use async context manager.")

        try:
            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"football-data.org HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"football-data.org request error: {e}")
            raise

    # Competitions
    async def get_competitions(self) -> List[Dict[str, Any]]:
        """Get all available competitions."""
        data = await self._request("/competitions")
        return data.get("competitions", [])

    async def get_competition(self, code: str) -> Optional[Dict[str, Any]]:
        """Get competition by code."""
        data = await self._request(f"/competitions/{code}")
        return data

    # Teams
    async def get_teams_by_competition(self, code: str, season: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get teams for a competition."""
        params = {}
        if season:
            params["season"] = season
        data = await self._request(f"/competitions/{code}/teams", params)
        return data.get("teams", [])

    async def get_team(self, team_id: int) -> Optional[Dict[str, Any]]:
        """Get team by ID."""
        data = await self._request(f"/teams/{team_id}")
        return data

    # Matches/Fixtures
    async def get_matches_by_competition(
        self, code: str, season: Optional[int] = None,
        date_from: Optional[str] = None, date_to: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get matches for a competition."""
        params = {}
        if season:
            params["season"] = season
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if status:
            params["status"] = status

        data = await self._request(f"/competitions/{code}/matches", params)
        return data.get("matches", [])

    async def get_matches_by_date_range(
        self, date_from: str, date_to: str,
        competition_codes: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get matches across competitions for a date range."""
        params = {
            "dateFrom": date_from,
            "dateTo": date_to,
        }
        if competition_codes:
            params["competitions"] = ",".join(competition_codes)

        data = await self._request("/matches", params)
        return data.get("matches", [])

    async def get_match(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Get match by ID."""
        data = await self._request(f"/matches/{match_id}")
        return data

    # Standings
    async def get_standings(self, code: str, season: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get competition standings."""
        params = {}
        if season:
            params["season"] = season
        data = await self._request(f"/competitions/{code}/standings", params)
        return data.get("standings", [])

    # Scorers
    async def get_scorers(self, code: str, season: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top scorers for a competition."""
        params = {"limit": limit}
        if season:
            params["season"] = season
        data = await self._request(f"/competitions/{code}/scorers", params)
        return data.get("scorers", [])


class FootballDataNormalizer:
    """Normalize football-data.org data to internal models."""

    # Map football-data.org competition codes to our internal IDs
    CODE_TO_INTERNAL_ID = {
        "PL": 39,
        "PD": 140,
        "BL1": 78,
        "SA": 135,
        "FL1": 61,
        "CL": 2,
        "EL": 3,
    }

    @staticmethod
    def normalize_competition(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize competition data."""
        return {
            "id": FootballDataNormalizer.CODE_TO_INTERNAL_ID.get(data.get("code")),
            "name": data.get("name"),
            "country": data.get("area", {}).get("name"),
            "logo_url": data.get("emblem"),
            "type": data.get("type"),
            "current_season": data.get("currentSeason", {}).get("id") if data.get("currentSeason") else None,
            "is_active": True,
        }

    @staticmethod
    def normalize_team(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize team data."""
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "short_name": data.get("shortName") or data.get("tla"),
            "country": data.get("area", {}).get("name"),
            "logo_url": data.get("crest"),
            "venue_name": data.get("venue"),
            "venue_city": None,
            "venue_capacity": None,
            "founded": data.get("founded"),
            "is_national": False,
        }

    @staticmethod
    def normalize_fixture(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize fixture/match data."""
        competition = data.get("competition", {})
        season = data.get("season", {})
        home_team = data.get("homeTeam", {})
        away_team = data.get("awayTeam", {})
        score = data.get("score", {})

        # Map status
        status_map = {
            "SCHEDULED": "NS",
            "TIMED": "NS",
            "IN_PLAY": "1H",
            "PAUSED": "HT",
            "FINISHED": "FT",
            "POSTPONED": "PST",
            "SUSPENDED": "SUSP",
            "CANCELLED": "CANC",
        }

        return {
            "id": data.get("id"),
            "season": season.get("id") if isinstance(season.get("id"), int) else season.get("startDate", "")[:4],
            "home_team_id": home_team.get("id"),
            "away_team_id": away_team.get("id"),
            "date": data.get("utcDate"),
            "timestamp": int(datetime.fromisoformat(data.get("utcDate").replace("Z", "+00:00")).timestamp()) if data.get("utcDate") else None,
            "timezone": "UTC",
            "venue_id": None,
            "referee_id": None,
            "status_short": status_map.get(data.get("status"), "NS"),
            "status_long": data.get("status"),
            "status_elapsed': data.get("minute"),
            "round": data.get("matchday"),
        }

    @staticmethod
    def normalize_standings(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize standings data."""
        normalized = []
        for standing in data:
            stage = standing.get("stage", "REGULAR_SEASON")
            table = standing.get("table", [])
            for entry in table:
                team = entry.get("team", {})
                normalized.append({
                    "team_id": team.get("id"),
                    "position": entry.get("position"),
                    "played": entry.get("playedGames"),
                    "won": entry.get("won"),
                    "draw": entry.get("draw"),
                    "lost": entry.get("lost"),
                    "points": entry.get("points"),
                    "goals_for": entry.get("goalsFor"),
                    "goals_against": entry.get("goalsAgainst"),
                    "goal_difference": entry.get("goalDifference"),
                    "form": entry.get("form"),
                })
        return normalized