"""The Odds API provider for historical odds data."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class OddsAPIClient:
    """Client for The Odds API."""

    # Sport key for soccer
    SPORT_KEY = "soccer"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ODDS_API_KEY
        self.base_url = settings.ODDS_API_BASE_URL
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def _request(self, endpoint: str, params: Dict[str, Any] = None) -> Any:
        """Make a request to the API."""
        if not self.client:
            raise Exception("Client not initialized. Use async context manager.")

        request_params = params or {}
        request_params["apiKey"] = self.api_key

        try:
            response = await self.client.get(endpoint, params=request_params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"The Odds API HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"The Odds API request error: {e}")
            raise

    async def get_sports(self) -> List[Dict[str, Any]]:
        """Get available sports."""
        return await self._request("/sports")

    async def get_odds(
        self,
        sport: str = None,
        regions: str = "us,uk,eu,au",
        markets: str = "h2h,spreads,totals",
        odds_format: str = "decimal",
        date_format: str = "iso",
        bookmakers: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get odds for a sport."""
        sport = sport or self.SPORT_KEY
        params = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": date_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers

        return await self._request(f"/sports/{sport}/odds", params)

    async def get_historical_odds(
        self,
        sport: str = None,
        regions: str = "us,uk,eu,au",
        markets: str = "h2h,spreads,totals",
        odds_format: str = "decimal",
        date: Optional[str] = None,
        bookmakers: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get historical odds for a sport on a specific date."""
        sport = sport or self.SPORT_KEY
        params = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }
        if date:
            params["date"] = date
        if bookmakers:
            params["bookmakers"] = bookmakers

        return await self._request(f"/sports/{sport}/odds-history", params)

    async def get_event_odds(
        self,
        event_id: str,
        regions: str = "us,uk,eu,au",
        markets: str = "h2h,spreads,totals",
        odds_format: str = "decimal",
        bookmakers: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get odds for a specific event."""
        params = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers

        return await self._request(f"/sports/{self.SPORT_KEY}/events/{event_id}/odds", params)

    async def get_historical_event_odds(
        self,
        event_id: str,
        date: str,
        regions: str = "us,uk,eu,au",
        markets: str = "h2h,spreads,totals",
        odds_format: str = "decimal",
    ) -> Dict[str, Any]:
        """Get historical odds for a specific event on a specific date."""
        params = {
            "date": date,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }
        return await self._request(f"/sports/{self.SPORT_KEY}/events/{event_id}/odds-history", params)


class OddsAPINormalizer:
    """Normalize The Odds API data to internal models."""

    # Bookmaker name to ID mapping (would be populated from database)
    BOOKMAKER_NAME_TO_ID = {}

    @staticmethod
    def normalize_odds(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize odds data from The Odds API."""
        normalized = []

        for event in data:
            event_id = event.get("id")
            sport_key = event.get("sport_key")
            sport_title = event.get("sport_title")
            commence_time = event.get("commence_time")
            home_team = event.get("home_team")
            away_team = event.get("away_team")
            bookmakers = event.get("bookmakers", [])

            for bookmaker in bookmakers:
                bookmaker_key = bookmaker.get("key")
                bookmaker_title = bookmaker.get("title")
                markets = bookmaker.get("markets", [])

                for market in markets:
                    market_key = market.get("key")  # h2h, spreads, totals
                    outcomes = market.get("outcomes", [])

                    if market_key == "h2h":
                        # Match winner / 1X2
                        odd_home = odd_draw = odd_away = None
                        for outcome in outcomes:
                            name = outcome.get("name", "").lower()
                            price = outcome.get("price")
                            if name == home_team.lower():
                                odd_home = price
                            elif name == away_team.lower():
                                odd_away = price
                            elif name == "draw":
                                odd_draw = price

                        normalized.append({
                            "event_id": event_id,
                            "bookmaker_key": bookmaker_key,
                            "bookmaker_title": bookmaker_title,
                            "market_type": "match_winner",
                            "market_name": "Match Winner",
                            "value": None,
                            "odd_home": odd_home,
                            "odd_draw": odd_draw,
                            "odd_away": odd_away,
                            "commence_time": commence_time,
                            "home_team": home_team,
                            "away_team": away_team,
                        })

                    elif market_key == "totals":
                        # Over/Under
                        for outcome in outcomes:
                            name = outcome.get("name", "").lower()
                            price = outcome.get("price")
                            point = outcome.get("point")

                            if "over" in name:
                                normalized.append({
                                    "event_id": event_id,
                                    "bookmaker_key": bookmaker_key,
                                    "bookmaker_title": bookmaker_title,
                                    "market_type": "over_under",
                                    "market_name": f"Over {point}",
                                    "value": str(point),
                                    "odd_home": price,  # Over
                                    "odd_draw": None,
                                    "odd_away": None,  # Under would be separate
                                    "commence_time": commence_time,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                })
                            elif "under" in name:
                                normalized.append({
                                    "event_id": event_id,
                                    "bookmaker_key": bookmaker_key,
                                    "bookmaker_title": bookmaker_title,
                                    "market_type": "over_under",
                                    "market_name": f"Under {point}",
                                    "value": str(point),
                                    "odd_home": None,
                                    "odd_draw": None,
                                    "odd_away": price,  # Under
                                    "commence_time": commence_time,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                })

                    elif market_key == "spreads":
                        # Asian Handicap / Spreads
                        for outcome in outcomes:
                            name = outcome.get("name", "").lower()
                            price = outcome.get("price")
                            point = outcome.get("point")

                            normalized.append({
                                "event_id": event_id,
                                "bookmaker_key": bookmaker_key,
                                "bookmaker_title": bookmaker_title,
                                "market_type": "asian_handicap",
                                "market_name": f"{name} {point}",
                                "value": str(abs(point)) if point else None,
                                "odd_home": price if home_team.lower() in name else None,
                                "odd_draw": None,
                                "odd_away": price if away_team.lower() in name else None,
                                "odd_handicap": point,
                                "commence_time": commence_time,
                                "home_team": home_team,
                                "away_team": away_team,
                            })

        return normalized