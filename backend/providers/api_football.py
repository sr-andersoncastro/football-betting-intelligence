"""API-Football provider for football data."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from config.settings import settings

logger = logging.getLogger(__name__)


class APIFootballResponse(BaseModel):
    """Standard API-Football response structure."""
    get: str
    parameters: Dict[str, Any]
    errors: List[Any]
    results: int
    paging: Dict[str, int]
    response: List[Any]


class APIFootballClient:
    """Client for API-Football (api-football.com)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.API_FOOTBALL_KEY
        self.base_url = settings.API_FOOTBALL_BASE_URL
        self.rate_limit = settings.API_FOOTBALL_RATE_LIMIT
        self._requests_today = 0
        self._last_reset = datetime.now().date()
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-rapidapi-key": self.api_key,
                "x-rapidapi-host": "v3.football.api-sports.io",
            },
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        today = datetime.now().date()
        if today != self._last_reset:
            self._requests_today = 0
            self._last_reset = today
        return self._requests_today < self.rate_limit

    async def _request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a request to the API."""
        if not self._check_rate_limit():
            raise Exception(f"Rate limit exceeded: {self.rate_limit} requests per day")

        if not self.client:
            raise Exception("Client not initialized. Use async context manager.")

        self._requests_today += 1

        try:
            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"API-Football HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"API-Football request error: {e}")
            raise

    # Competitions
    async def get_competitions(self) -> List[Dict[str, Any]]:
        """Get all competitions."""
        data = await self._request("/leagues")
        return data.get("response", [])

    async def get_competition_by_id(self, league_id: int) -> Optional[Dict[str, Any]]:
        """Get competition by ID."""
        data = await self._request("/leagues", {"id": league_id})
        results = data.get("response", [])
        return results[0] if results else None

    # Teams
    async def get_teams_by_league(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Get teams for a league and season."""
        data = await self._request("/teams", {"league": league_id, "season": season})
        return data.get("response", [])

    async def get_team_by_id(self, team_id: int) -> Optional[Dict[str, Any]]:
        """Get team by ID."""
        data = await self._request("/teams", {"id": team_id})
        results = data.get("response", [])
        return results[0] if results else None

    # Fixtures
    async def get_fixtures_by_league_date(
        self, league_id: int, season: int, date: str
    ) -> List[Dict[str, Any]]:
        """Get fixtures for a league on a specific date."""
        data = await self._request("/fixtures", {
            "league": league_id,
            "season": season,
            "date": date,
        })
        return data.get("response", [])

    async def get_fixtures_by_league_season(
        self, league_id: int, season: int, next_days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get fixtures for a league and season."""
        data = await self._request("/fixtures", {
            "league": league_id,
            "season": season,
            "next": next_days,
        })
        return data.get("response", [])

    async def get_fixtures_by_date_range(
        self, league_id: int, season: int, from_date: str, to_date: str
    ) -> List[Dict[str, Any]]:
        """Get fixtures for a league within date range."""
        data = await self._request("/fixtures", {
            "league": league_id,
            "season": season,
            "from": from_date,
            "to": to_date,
        })
        return data.get("response", [])

    async def get_fixture_by_id(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Get fixture by ID."""
        data = await self._request("/fixtures", {"id": fixture_id})
        results = data.get("response", [])
        return results[0] if results else None

    async def get_fixture_statistics(self, fixture_id: int) -> List[Dict[str, Any]]:
        """Get fixture statistics."""
        data = await self._request("/fixtures/statistics", {"fixture": fixture_id})
        return data.get("response", [])

    async def get_fixture_events(self, fixture_id: int) -> List[Dict[str, Any]]:
        """Get fixture events (goals, cards, etc.)."""
        data = await self._request("/fixtures/events", {"fixture": fixture_id})
        return data.get("response", [])

    async def get_fixture_lineups(self, fixture_id: int) -> List[Dict[str, Any]]:
        """Get fixture lineups."""
        data = await self._request("/fixtures/lineups", {"fixture": fixture_id})
        return data.get("response", [])

    # Players
    async def get_players_by_team_season(self, team_id: int, season: int) -> List[Dict[str, Any]]:
        """Get players for a team and season."""
        data = await self._request("/players", {"team": team_id, "season": season})
        return data.get("response", [])

    # Odds
    async def get_odds_by_fixture(self, fixture_id: int) -> List[Dict[str, Any]]:
        """Get odds for a fixture."""
        data = await self._request("/odds", {"fixture": fixture_id})
        return data.get("response", [])

    async def get_odds_by_league_season(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Get odds for a league and season."""
        data = await self._request("/odds", {"league": league_id, "season": season})
        return data.get("response", [])

    # Standings
    async def get_standings(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Get league standings."""
        data = await self._request("/standings", {"league": league_id, "season": season})
        return data.get("response", [])

    # Team Statistics
    async def get_team_statistics(self, team_id: int, league_id: int, season: int) -> Dict[str, Any]:
        """Get team statistics for a season."""
        data = await self._request("/teams/statistics", {
            "team": team_id,
            "league": league_id,
            "season": season,
        })
        results = data.get("response", [])
        return results[0] if results else {}

    # Referee
    async def get_referees_by_league(self, league_id: int) -> List[Dict[str, Any]]:
        """Get referees for a league."""
        data = await self._request("/referees", {"league": league_id})
        return data.get("response", [])


class APIFootballNormalizer:
    """Normalize API-Football data to internal models."""

    @staticmethod
    def normalize_competition(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize competition data."""
        league = data.get("league", {})
        country = data.get("country", {})
        return {
            "id": league.get("id"),
            "name": league.get("name"),
            "country": country.get("name"),
            "logo_url": league.get("logo"),
            "type": league.get("type"),
            "current_season": league.get("season", 0) if isinstance(league.get("season"), int) else 0,
            "is_active": True,
        }

    @staticmethod
    def normalize_team(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize team data."""
        team = data.get("team", {})
        venue = data.get("venue", {})
        return {
            "id": team.get("id"),
            "name": team.get("name"),
            "short_name": team.get("code"),
            "country": team.get("country"),
            "logo_url": team.get("logo"),
            "venue_name": venue.get("name"),
            "venue_city": venue.get("city"),
            "venue_capacity": venue.get("capacity"),
            "founded": team.get("founded"),
            "is_national": team.get("national", False),
        }

    @staticmethod
    def normalize_fixture(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize fixture data."""
        fixture = data.get("fixture", {})
        league = data.get("league", {})
        teams = data.get("teams", {})
        goals = data.get("goals", {})
        score = data.get("score", {})

        home = teams.get("home", {})
        away = teams.get("away", {})

        return {
            "id": fixture.get("id"),
            "season": league.get("season"),
            "home_team_id": home.get("id"),
            "away_team_id": away.get("id"),
            "date": fixture.get("date"),
            "timestamp": fixture.get("timestamp"),
            "timezone": fixture.get("timezone"),
            "venue_id": fixture.get("venue", {}).get("id"),
            "referee_id": None,  # Would need separate lookup
            "status_short": fixture.get("status", {}).get("short"),
            "status_long": fixture.get("status", {}).get("long"),
            "status_elapsed": fixture.get("status", {}).get("elapsed"),
            "round": league.get("round"),
        }

    @staticmethod
    def normalize_statistics(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize fixture statistics."""
        normalized = []
        for team_stat in data:
            team = team_stat.get("team", {})
            stats = team_stat.get("statistics", [])
            for stat in stats:
                normalized.append({
                    "team_id": team.get("id"),
                    "type": stat.get("type"),
                    "value": str(stat.get("value")) if stat.get("value") is not None else None,
                })
        return normalized

    @staticmethod
    def normalize_events(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize fixture events."""
        normalized = []
        for event in data:
            time_info = event.get("time", {})
            team = event.get("team", {})
            player = event.get("player", {})
            normalized.append({
                "team_id": team.get("id"),
                "player_id": player.get("id"),
                "time_elapsed": time_info.get("elapsed"),
                "time_extra": time_info.get("extra"),
                "type": event.get("type"),
                "detail": event.get("detail"),
                "comments": event.get("comments"),
            })
        return normalized

    @staticmethod
    def normalize_lineups(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize fixture lineups."""
        normalized = []
        for lineup in data:
            team = lineup.get("team", {})
            formation = lineup.get("formation")
            start_xi = lineup.get("startXI", [])
            substitutes = lineup.get("substitutes", [])

            for player_data in start_xi:
                player = player_data.get("player", {})
                normalized.append({
                    "team_id": team.get("id"),
                    "formation": formation,
                    "is_starting": True,
                    "player_id": player.get("id"),
                    "number": player_data.get("number"),
                    "position": player_data.get("pos"),
                    "grid": player_data.get("grid"),
                })

            for player_data in substitutes:
                player = player_data.get("player", {})
                normalized.append({
                    "team_id": team.get("id"),
                    "formation": formation,
                    "is_starting": False,
                    "player_id": player.get("id"),
                    "number": player_data.get("number"),
                    "position": player_data.get("pos"),
                    "grid": player_data.get("grid"),
                })
        return normalized

    @staticmethod
    def normalize_odds(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize odds data."""
        normalized = []
        for bookmaker_data in data:
            bookmaker = bookmaker_data.get("bookmaker", {})
            bets = bookmaker_data.get("bets", [])

            for bet in bets:
                bet_name = bet.get("name", "").lower()
                values = bet.get("values", [])

                # Map bet names to market types
                market_type = None
                market_name = bet.get("name")
                value_str = None

                if "match winner" in bet_name or "1x2" in bet_name:
                    market_type = "match_winner"
                elif "over" in bet_name and "under" in bet_name:
                    market_type = "over_under"
                elif "both teams" in bet_name and "score" in bet_name:
                    market_type = "both_teams_score"
                elif "asian handicap" in bet_name or "handicap" in bet_name:
                    market_type = "asian_handicap"
                elif "corner" in bet_name:
                    market_type = "corners"
                elif "card" in bet_name:
                    market_type = "cards"

                # Extract line value for handicap/over-under
                if market_type in ["over_under", "asian_handicap", "corners"]:
                    import re
                    match = re.search(r"([\d.]+)", bet_name)
                    if match:
                        value_str = match.group(1)

                odd_home = odd_draw = odd_away = None
                for val in values:
                    v = val.get("value", "").lower()
                    odd = val.get("odd")
                    if v in ["1", "home", "over", "yes"]:
                        odd_home = float(odd) if odd else None
                    elif v in ["x", "draw"]:
                        odd_draw = float(odd) if odd else None
                    elif v in ["2", "away", "under", "no"]:
                        odd_away = float(odd) if odd else None

                if market_type:
                    normalized.append({
                        "bookmaker_id": bookmaker.get("id"),
                        "market_type": market_type,
                        "market_name": market_name,
                        "value": value_str,
                        "odd_home": odd_home,
                        "odd_draw": odd_draw,
                        "odd_away": odd_away,
                    })
        return normalized

    @staticmethod
    def normalize_bookmaker(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize bookmaker data."""
        bookmaker = data.get("bookmaker", {})
        return {
            "id": bookmaker.get("id"),
            "name": bookmaker.get("name"),
            "logo_url": None,  # Not provided
            "is_active": True,
        }

    @staticmethod
    def normalize_player(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize player data."""
        player = data.get("player", {})
        statistics = data.get("statistics", [{}])[0] if data.get("statistics") else {}

        games = statistics.get("games", {})
        goals = statistics.get("goals", {})
        cards = statistics.get("cards", {})
        shots = statistics.get("shots", {})
        passes = statistics.get("passes", {})

        return {
            "id": player.get("id"),
            "name": player.get("name"),
            "firstname": player.get("firstname"),
            "lastname": player.get("lastname"),
            "age": player.get("age"),
            "birth_date": player.get("birth", {}).get("date"),
            "birth_place": player.get("birth", {}).get("place"),
            "birth_country": player.get("birth", {}).get("country"),
            "nationality": player.get("nationality"),
            "height": player.get("height"),
            "weight": player.get("weight"),
            "photo_url": player.get("photo"),
        }