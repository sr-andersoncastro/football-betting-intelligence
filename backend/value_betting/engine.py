"""Value Betting engine for identifying profitable betting opportunities."""
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum

from config.settings import settings


class BetSelection(Enum):
    """Possible bet selections."""
    HOME = "home"
    DRAW = "draw"
    AWAY = "away"
    OVER = "over"
    UNDER = "under"
    BTTS_YES = "btts_yes"
    BTTS_NO = "btts_no"
    HOME_HANDICAP = "home_handicap"
    AWAY_HANDICAP = "away_handicap"
    HOME_CORNERS = "home_corners"
    AWAY_CORNERS = "away_corners"
    OVER_CORNERS = "over_corners"
    UNDER_CORNERS = "under_corners"
    HOME_CARDS = "home_cards"
    AWAY_CARDS = "away_cards"
    OVER_CARDS = "over_cards"
    UNDER_CARDS = "under_cards"


@dataclass
class OddsData:
    """Odds data for a market."""
    market_type: str
    market_line: Optional[str]
    bookmaker_id: int
    bookmaker_name: str
    odd_home: Optional[float]
    odd_draw: Optional[float]
    odd_away: Optional[float]
    odd_over: Optional[float]
    odd_under: Optional[float]
    odd_btts_yes: Optional[float]
    odd_btts_no: Optional[float]
    odd_handicap: Optional[float]
    timestamp: datetime
    is_live: bool = False


@dataclass
class ModelProbabilities:
    """Model probabilities for a fixture."""
    fixture_id: int
    model_version: str
    prob_home: float
    prob_draw: float
    prob_away: float
    prob_over: Dict[float, float]  # line -> prob
    prob_under: Dict[float, float]
    prob_btts_yes: float
    prob_btts_no: float
    prob_home_corners: Dict[float, float]
    prob_away_corners: Dict[float, float]
    prob_over_corners: Dict[float, float]
    prob_home_cards: Dict[float, float]
    prob_away_cards: Dict[float, float]
    prob_over_cards: Dict[float, float]
    confidence: float
    data_quality: float


@dataclass
class ValueBet:
    """Identified value betting opportunity."""
    fixture_id: int
    selection: BetSelection
    market_type: str
    market_line: Optional[str]
    model_probability: float
    implied_probability: float
    edge: float  # model_prob - implied_prob
    expected_value: float  # (model_prob * odd) - 1
    odd: float
    bookmaker_id: int
    bookmaker_name: str
    confidence: float
    kelly_stake: float
    fractional_kelly_stake: float
    timestamp: datetime
    is_live: bool = False
    metadata: Dict = field(default_factory=dict)


class ValueBettingEngine:
    """Engine for calculating value bets."""

    def __init__(self):
        self.min_edge = settings.MIN_EDGE_PERCENT / 100
        self.min_ev = settings.MIN_EV_PERCENT / 100
        self.max_kelly = settings.MAX_KELLY_FRACTION
        self.confidence_threshold = settings.CONFIDENCE_THRESHOLD

    def calculate_implied_probabilities(
        self,
        odd_home: Optional[float],
        odd_draw: Optional[float],
        odd_away: Optional[float],
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate implied probabilities removing bookmaker margin."""
        odds = []
        if odd_home:
            odds.append(("home", odd_home))
        if odd_draw:
            odds.append(("draw", odd_draw))
        if odd_away:
            odds.append(("away", odd_away))

        if not odds:
            return None, None, None

        # Calculate raw implied probabilities
        implied = {name: 1.0 / odd for name, odd in odds}
        total = sum(implied.values())

        # Remove margin proportionally (Shin method approximation)
        if total > 1.0:
            margin = total - 1.0
            for name in implied:
                implied[name] = implied[name] * (1 - margin / total)

        return (
            implied.get("home"),
            implied.get("draw"),
            implied.get("away"),
        )

    def calculate_implied_over_under(
        self,
        odd_over: Optional[float],
        odd_under: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate implied probabilities for over/under."""
        if not odd_over or not odd_under:
            return None, None

        implied_over = 1.0 / odd_over
        implied_under = 1.0 / odd_under
        total = implied_over + implied_under

        if total > 1.0:
            implied_over /= total
            implied_under /= total

        return implied_over, implied_under

    def calculate_implied_btts(
        self,
        odd_yes: Optional[float],
        odd_no: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        """Calculate implied probabilities for BTTS."""
        if not odd_yes or not odd_no:
            return None, None

        implied_yes = 1.0 / odd_yes
        implied_no = 1.0 / odd_no
        total = implied_yes + implied_no

        if total > 1.0:
            implied_yes /= total
            implied_no /= total

        return implied_yes, implied_no

    def calculate_kelly_stake(
        self,
        model_prob: float,
        odd: float,
        fraction: float = None,
    ) -> float:
        """Calculate Kelly criterion stake."""
        if fraction is None:
            fraction = self.max_kelly

        if model_prob <= 0 or odd <= 1:
            return 0.0

        # Kelly formula: f* = (bp - q) / b
        # where b = odd - 1, p = model_prob, q = 1 - model_prob
        b = odd - 1
        p = model_prob
        q = 1 - p

        kelly = (b * p - q) / b
        return max(0, kelly * fraction)

    def evaluate_match_winner(
        self,
        odds: OddsData,
        model_probs: ModelProbabilities,
    ) -> List[ValueBet]:
        """Evaluate 1X2 market for value."""
        value_bets = []

        implied_home, implied_draw, implied_away = self.calculate_implied_probabilities(
            odds.odd_home, odds.odd_draw, odds.odd_away
        )

        if implied_home is None:
            return value_bets

        # Home
        edge_home = model_probs.prob_home - implied_home
        ev_home = (model_probs.prob_home * odds.odd_home) - 1 if odds.odd_home else -1

        if edge_home >= self.min_edge and ev_home >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_probs.prob_home, odds.odd_home)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.HOME,
                market_type="match_winner",
                market_line=None,
                model_probability=model_probs.prob_home,
                implied_probability=implied_home,
                edge=edge_home,
                expected_value=ev_home,
                odd=odds.odd_home,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        # Draw
        edge_draw = model_probs.prob_draw - implied_draw
        ev_draw = (model_probs.prob_draw * odds.odd_draw) - 1 if odds.odd_draw else -1

        if edge_draw >= self.min_edge and ev_draw >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_probs.prob_draw, odds.odd_draw)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.DRAW,
                market_type="match_winner",
                market_line=None,
                model_probability=model_probs.prob_draw,
                implied_probability=implied_draw,
                edge=edge_draw,
                expected_value=ev_draw,
                odd=odds.odd_draw,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        # Away
        edge_away = model_probs.prob_away - implied_away
        ev_away = (model_probs.prob_away * odds.odd_away) - 1 if odds.odd_away else -1

        if edge_away >= self.min_edge and ev_away >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_probs.prob_away, odds.odd_away)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.AWAY,
                market_type="match_winner",
                market_line=None,
                model_probability=model_probs.prob_away,
                implied_probability=implied_away,
                edge=edge_away,
                expected_value=ev_away,
                odd=odds.odd_away,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        return value_bets

    def evaluate_over_under(
        self,
        odds: OddsData,
        model_probs: ModelProbabilities,
    ) -> List[ValueBet]:
        """Evaluate Over/Under markets for value."""
        value_bets = []

        if not odds.odd_over or not odds.odd_under:
            return value_bets

        line = float(odds.market_line) if odds.market_line else 2.5
        model_over = model_probs.prob_over.get(line, 0)
        model_under = model_probs.prob_under.get(line, 0)

        implied_over, implied_under = self.calculate_implied_over_under(
            odds.odd_over, odds.odd_under
        )

        if implied_over is None:
            return value_bets

        # Over
        edge_over = model_over - implied_over
        ev_over = (model_over * odds.odd_over) - 1

        if edge_over >= self.min_edge and ev_over >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_over, odds.odd_over)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.OVER,
                market_type="over_under",
                market_line=str(line),
                model_probability=model_over,
                implied_probability=implied_over,
                edge=edge_over,
                expected_value=ev_over,
                odd=odds.odd_over,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        # Under
        edge_under = model_under - implied_under
        ev_under = (model_under * odds.odd_under) - 1

        if edge_under >= self.min_edge and ev_under >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_under, odds.odd_under)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.UNDER,
                market_type="over_under",
                market_line=str(line),
                model_probability=model_under,
                implied_probability=implied_under,
                edge=edge_under,
                expected_value=ev_under,
                odd=odds.odd_under,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        return value_bets

    def evaluate_btts(
        self,
        odds: OddsData,
        model_probs: ModelProbabilities,
    ) -> List[ValueBet]:
        """Evaluate Both Teams To Score market for value."""
        value_bets = []

        if not odds.odd_btts_yes or not odds.odd_btts_no:
            return value_bets

        implied_yes, implied_no = self.calculate_implied_btts(
            odds.odd_btts_yes, odds.odd_btts_no
        )

        if implied_yes is None:
            return value_bets

        # Yes
        edge_yes = model_probs.prob_btts_yes - implied_yes
        ev_yes = (model_probs.prob_btts_yes * odds.odd_btts_yes) - 1

        if edge_yes >= self.min_edge and ev_yes >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_probs.prob_btts_yes, odds.odd_btts_yes)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.BTTS_YES,
                market_type="both_teams_score",
                market_line=None,
                model_probability=model_probs.prob_btts_yes,
                implied_probability=implied_yes,
                edge=edge_yes,
                expected_value=ev_yes,
                odd=odds.odd_btts_yes,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        # No
        edge_no = model_probs.prob_btts_no - implied_no
        ev_no = (model_probs.prob_btts_no * odds.odd_btts_no) - 1

        if edge_no >= self.min_edge and ev_no >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_probs.prob_btts_no, odds.odd_btts_no)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.BTTS_NO,
                market_type="both_teams_score",
                market_line=None,
                model_probability=model_probs.prob_btts_no,
                implied_probability=implied_no,
                edge=edge_no,
                expected_value=ev_no,
                odd=odds.odd_btts_no,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        return value_bets

    def evaluate_corners(
        self,
        odds: OddsData,
        model_probs: ModelProbabilities,
    ) -> List[ValueBet]:
        """Evaluate Corners markets for value."""
        value_bets = []

        if not odds.odd_over or not odds.odd_under:
            return value_bets

        line = float(odds.market_line) if odds.market_line else 9.5
        model_over = model_probs.prob_over_corners.get(line, 0)
        model_under = 1 - model_over

        implied_over, implied_under = self.calculate_implied_over_under(
            odds.odd_over, odds.odd_under
        )

        if implied_over is None:
            return value_bets

        # Over
        edge_over = model_over - implied_over
        ev_over = (model_over * odds.odd_over) - 1

        if edge_over >= self.min_edge and ev_over >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_over, odds.odd_over)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.OVER_CORNERS,
                market_type="corners",
                market_line=str(line),
                model_probability=model_over,
                implied_probability=implied_over,
                edge=edge_over,
                expected_value=ev_over,
                odd=odds.odd_over,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        # Under
        edge_under = model_under - implied_under
        ev_under = (model_under * odds.odd_under) - 1

        if edge_under >= self.min_edge and ev_under >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_under, odds.odd_under)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.UNDER_CORNERS,
                market_type="corners",
                market_line=str(line),
                model_probability=model_under,
                implied_probability=implied_under,
                edge=edge_under,
                expected_value=ev_under,
                odd=odds.odd_under,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        return value_bets

    def evaluate_cards(
        self,
        odds: OddsData,
        model_probs: ModelProbabilities,
    ) -> List[ValueBet]:
        """Evaluate Cards markets for value."""
        value_bets = []

        if not odds.odd_over or not odds.odd_under:
            return value_bets

        line = float(odds.market_line) if odds.market_line else 4.5
        model_over = model_probs.prob_over_cards.get(line, 0)
        model_under = 1 - model_over

        implied_over, implied_under = self.calculate_implied_over_under(
            odds.odd_over, odds.odd_under
        )

        if implied_over is None:
            return value_bets

        # Over
        edge_over = model_over - implied_over
        ev_over = (model_over * odds.odd_over) - 1

        if edge_over >= self.min_edge and ev_over >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_over, odds.odd_over)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.OVER_CARDS,
                market_type="cards",
                market_line=str(line),
                model_probability=model_over,
                implied_probability=implied_over,
                edge=edge_over,
                expected_value=ev_over,
                odd=odds.odd_over,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        # Under
        edge_under = model_under - implied_under
        ev_under = (model_under * odds.odd_under) - 1

        if edge_under >= self.min_edge and ev_under >= self.min_ev:
            kelly = self.calculate_kelly_stake(model_under, odds.odd_under)
            value_bets.append(ValueBet(
                fixture_id=model_probs.fixture_id,
                selection=BetSelection.UNDER_CARDS,
                market_type="cards",
                market_line=str(line),
                model_probability=model_under,
                implied_probability=implied_under,
                edge=edge_under,
                expected_value=ev_under,
                odd=odds.odd_under,
                bookmaker_id=odds.bookmaker_id,
                bookmaker_name=odds.bookmaker_name,
                confidence=model_probs.confidence,
                kelly_stake=kelly,
                fractional_kelly_stake=kelly * self.max_kelly,
                timestamp=odds.timestamp,
                is_live=odds.is_live,
            ))

        return value_bets

    def find_all_value_bets(
        self,
        odds_list: List[OddsData],
        model_probs: ModelProbabilities,
    ) -> List[ValueBet]:
        """Find all value bets across all markets."""
        all_bets = []

        for odds in odds_list:
            # Skip if odds are stale (older than 30 minutes for pre-match, 5 minutes for live)
            age_minutes = (datetime.utcnow() - odds.timestamp).total_seconds() / 60
            max_age = 5 if odds.is_live else 30
            if age_minutes > max_age:
                continue

            # Skip if confidence too low
            if model_probs.confidence < self.confidence_threshold:
                continue

            # Skip if data quality too low
            if model_probs.data_quality < 0.5:
                continue

            # Evaluate each market
            if odds.market_type == "match_winner":
                all_bets.extend(self.evaluate_match_winner(odds, model_probs))
            elif odds.market_type == "over_under":
                all_bets.extend(self.evaluate_over_under(odds, model_probs))
            elif odds.market_type == "both_teams_score":
                all_bets.extend(self.evaluate_btts(odds, model_probs))
            elif odds.market_type == "corners":
                all_bets.extend(self.evaluate_corners(odds, model_probs))
            elif odds.market_type == "cards":
                all_bets.extend(self.evaluate_cards(odds, model_probs))

        # Sort by expected value descending
        all_bets.sort(key=lambda x: x.expected_value, reverse=True)

        return all_bets


class ArbitrageDetector:
    """Detect arbitrage opportunities across bookmakers."""

    def __init__(self, min_profit_percent: float = 0.5):
        self.min_profit = min_profit_percent / 100

    def find_arbitrage(
        self,
        odds_by_bookmaker: Dict[int, OddsData],
        market_type: str,
    ) -> List[Dict]:
        """Find arbitrage opportunities."""
        arbitrage_opps = []

        if market_type == "match_winner":
            # Need home, draw, away from potentially different bookmakers
            best_home = max(
                (o for o in odds_by_bookmaker.values() if o.odd_home),
                key=lambda x: x.odd_home,
                default=None,
            )
            best_draw = max(
                (o for o in odds_by_bookmaker.values() if o.odd_draw),
                key=lambda x: x.odd_draw,
                default=None,
            )
            best_away = max(
                (o for o in odds_by_bookmaker.values() if o.odd_away),
                key=lambda x: x.odd_away,
                default=None,
            )

            if best_home and best_draw and best_away:
                implied_sum = (
                    1 / best_home.odd_home +
                    1 / best_draw.odd_draw +
                    1 / best_away.odd_away
                )

                if implied_sum < 1 - self.min_profit:
                    profit = (1 - implied_sum) * 100
                    stakes = {
                        "home": (1 / best_home.odd_home) / implied_sum,
                        "draw": (1 / best_draw.odd_draw) / implied_sum,
                        "away": (1 / best_away.odd_away) / implied_sum,
                    }

                    arbitrage_opps.append({
                        "market_type": "match_winner",
                        "profit_percent": profit,
                        "stakes": stakes,
                        "odds": {
                            "home": {"odd": best_home.odd_home, "bookmaker": best_home.bookmaker_name},
                            "draw": {"odd": best_draw.odd_draw, "bookmaker": best_draw.bookmaker_name},
                            "away": {"odd": best_away.odd_away, "bookmaker": best_away.bookmaker_name},
                        },
                    })

        return arbitrage_opps