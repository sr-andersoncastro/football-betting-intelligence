"""Card prediction models."""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import poisson, nbinom


@dataclass
class CardsPrediction:
    """Card prediction result."""
    home_cards_mean: float
    away_cards_mean: float
    total_cards_mean: float
    over_under_probs: Dict[float, Tuple[float, float]]
    handicap_probs: Dict[float, Tuple[float, float]]
    red_card_prob_home: float
    red_card_prob_away: float


class CardsModel:
    """Model for predicting yellow/red cards."""

    def __init__(self, max_cards: int = 10):
        self.max_cards = max_cards
        self.team_card_stats: Dict[int, Dict] = {}
        self.referee_stats: Dict[int, Dict] = {}
        self.league_avg_home_cards: float = 2.1
        self.league_avg_away_cards: float = 2.5
        self.use_negative_binomial: bool = True

    def fit(
        self,
        fixtures: List[Dict],
        team_ids: List[int],
        referee_data: Optional[List[Dict]] = None,
    ):
        """Fit card model from historical fixtures."""
        # Initialize team stats
        for team_id in team_ids:
            self.team_card_stats[team_id] = {
                "home_yellow_for": [],
                "home_yellow_against": [],
                "away_yellow_for": [],
                "away_yellow_against": [],
                "home_red_for": [],
                "home_red_against": [],
                "away_red_for": [],
                "away_red_against": [],
            }

        # Initialize referee stats
        if referee_data:
            for ref in referee_data:
                ref_id = ref.get("id")
                if ref_id:
                    self.referee_stats[ref_id] = {
                        "yellow_per_game": ref.get("yellow_cards_per_game", 4.5),
                        "red_per_game": ref.get("red_cards_per_game", 0.2),
                        "home_bias": ref.get("home_bias", 0.0),
                    }

        # Collect card data from fixtures
        for f in fixtures:
            home_id = f.get("home_team_id")
            away_id = f.get("away_team_id")
            ref_id = f.get("referee_id")

            home_yellow = f.get("home_yellow_cards", 0)
            away_yellow = f.get("away_yellow_cards", 0)
            home_red = f.get("home_red_cards", 0)
            away_red = f.get("away_red_cards", 0)

            if home_id in self.team_card_stats:
                self.team_card_stats[home_id]["home_yellow_for"].append(home_yellow)
                self.team_card_stats[home_id]["home_yellow_against"].append(away_yellow)
                self.team_card_stats[home_id]["home_red_for"].append(home_red)
                self.team_card_stats[home_id]["home_red_against"].append(away_red)

            if away_id in self.team_card_stats:
                self.team_card_stats[away_id]["away_yellow_for"].append(away_yellow)
                self.team_card_stats[away_id]["away_yellow_against"].append(home_yellow)
                self.team_card_stats[away_id]["away_red_for"].append(away_red)
                self.team_card_stats[away_id]["away_red_against"].append(home_red)

        # Calculate averages
        for team_id, stats in self.team_card_stats.items():
            stats["avg_home_yellow_for"] = np.mean(stats["home_yellow_for"]) if stats["home_yellow_for"] else self.league_avg_home_cards
            stats["avg_home_yellow_against"] = np.mean(stats["home_yellow_against"]) if stats["home_yellow_against"] else self.league_avg_away_cards
            stats["avg_away_yellow_for"] = np.mean(stats["away_yellow_for"]) if stats["away_yellow_for"] else self.league_avg_away_cards
            stats["avg_away_yellow_against"] = np.mean(stats["away_yellow_against"]) if stats["away_yellow_against"] else self.league_avg_home_cards

            stats["avg_home_red_for"] = np.mean(stats["home_red_for"]) if stats["home_red_for"] else 0.1
            stats["avg_away_red_for"] = np.mean(stats["away_red_for"]) if stats["away_red_for"] else 0.15

            # Variance for negative binomial
            stats["var_home_yellow"] = np.var(stats["home_yellow_for"]) if len(stats["home_yellow_for"]) > 1 else stats["avg_home_yellow_for"]
            stats["var_away_yellow"] = np.var(stats["away_yellow_for"]) if len(stats["away_yellow_for"]) > 1 else stats["avg_away_yellow_for"]

    def predict_match(
        self,
        home_team_id: int,
        away_team_id: int,
        referee_id: Optional[int] = None,
        importance: float = 1.0,  # Match importance factor
        rivalry: bool = False,
    ) -> CardsPrediction:
        """Predict cards for a match."""
        home_stats = self.team_card_stats.get(home_team_id, {})
        away_stats = self.team_card_stats.get(away_team_id, {})
        ref_stats = self.referee_stats.get(referee_id, {}) if referee_id else {}

        # Base expected yellow cards
        home_yellow_base = (
            home_stats.get("avg_home_yellow_for", self.league_avg_home_cards) * 0.5
            + away_stats.get("avg_away_yellow_against", self.league_avg_home_cards) * 0.3
            + self.league_avg_home_cards * 0.2
        )

        away_yellow_base = (
            away_stats.get("avg_away_yellow_for", self.league_avg_away_cards) * 0.5
            + home_stats.get("avg_home_yellow_against", self.league_avg_away_cards) * 0.3
            + self.league_avg_away_cards * 0.2
        )

        # Referee adjustment
        ref_yellow_factor = 1.0
        if ref_stats:
            ref_yellow_factor = ref_stats.get("yellow_per_game", 4.5) / 4.5  # League average ~4.5

        # Importance adjustment (finals, derbies, etc.)
        importance_factor = 1.0 + (importance - 1.0) * 0.3

        # Rivalry adjustment
        rivalry_factor = 1.25 if rivalry else 1.0

        home_yellow_mean = home_yellow_base * ref_yellow_factor * importance_factor * rivalry_factor
        away_yellow_mean = away_yellow_base * ref_yellow_factor * importance_factor * rivalry_factor

        # Home bias from referee
        if ref_stats.get("home_bias", 0) > 0:
            home_yellow_mean *= (1 - ref_stats["home_bias"] * 0.1)
            away_yellow_mean *= (1 + ref_stats["home_bias"] * 0.1)

        total_yellow_mean = home_yellow_mean + away_yellow_mean

        # Red card probabilities (much rarer)
        home_red_base = home_stats.get("avg_home_red_for", 0.1)
        away_red_base = away_stats.get("avg_away_red_for", 0.15)
        ref_red_factor = ref_stats.get("red_per_game", 0.2) / 0.2 if ref_stats else 1.0

        home_red_prob = min(0.5, home_red_base * ref_red_factor * importance_factor * rivalry_factor)
        away_red_prob = min(0.5, away_red_base * ref_red_factor * importance_factor * rivalry_factor)

        # Over/Under for total cards (yellow + red)
        total_mean = total_yellow_mean + home_red_prob + away_red_prob
        over_under = {}
        for line in [3.5, 4.5, 5.5, 6.5]:
            over, under = self._calculate_over_under(total_mean, line)
            over_under[line] = (over, under)

        # Handicap for cards
        handicap = {}
        for line in [-1.5, -0.5, 0.5, 1.5]:
            home_prob, away_prob = self._calculate_handicap(home_yellow_mean, away_yellow_mean, line)
            handicap[line] = (home_prob, away_prob)

        return CardsPrediction(
            home_cards_mean=home_yellow_mean,
            away_cards_mean=away_yellow_mean,
            total_cards_mean=total_mean,
            over_under_probs=over_under,
            handicap_probs=handicap,
            red_card_prob_home=home_red_prob,
            red_card_prob_away=away_red_prob,
        )

    def _calculate_over_under(self, mean: float, line: float) -> Tuple[float, float]:
        """Calculate over/under probabilities using negative binomial."""
        if self.use_negative_binomial:
            var = mean * 1.5  # Cards are often overdispersed
            if var <= mean:
                var = mean + 0.1

            r = mean ** 2 / (var - mean)
            p = r / (r + mean)

            over = 1 - nbinom.cdf(int(line), r, p)
            under = nbinom.cdf(int(line), r, p)
        else:
            over = 1 - poisson.cdf(int(line), mean)
            under = poisson.cdf(int(line), mean)

        return over, under

    def _calculate_handicap(
        self, home_mean: float, away_mean: float, line: float
    ) -> Tuple[float, float]:
        """Calculate Asian handicap probabilities for cards."""
        home_probs = self._get_distribution(home_mean)
        away_probs = self._get_distribution(away_mean)

        home_win = 0.0
        away_win = 0.0

        for h_cards, h_prob in home_probs.items():
            for a_cards, a_prob in away_probs.items():
                diff = h_cards - a_cards + line
                prob = h_prob * a_prob
                if diff > 0:
                    home_win += prob
                elif diff < 0:
                    away_win += prob

        total = home_win + away_win
        if total > 0:
            home_win /= total
            away_win /= total

        return home_win, away_win

    def _get_distribution(self, mean: float) -> Dict[int, float]:
        """Get probability distribution for cards."""
        dist = {}
        if self.use_negative_binomial:
            var = mean * 1.5
            if var <= mean:
                var = mean + 0.1
            r = mean ** 2 / (var - mean)
            p = r / (r + mean)

            for k in range(self.max_cards + 1):
                dist[k] = nbinom.pmf(k, r, p)
        else:
            for k in range(self.max_cards + 1):
                dist[k] = poisson.pmf(k, mean)

        return dist


class CardsModelAdvanced(CardsModel):
    """Advanced card model with player and tactical features."""

    def __init__(self, max_cards: int = 10):
        super().__init__(max_cards)
        self.player_card_rates: Dict[int, float] = {}  # player_id -> cards per 90

    def fit(
        self,
        fixtures: List[Dict],
        team_ids: List[int],
        referee_data: Optional[List[Dict]] = None,
        player_data: Optional[List[Dict]] = None,
    ):
        """Fit with player-level data."""
        super().fit(fixtures, team_ids, referee_data)

        # Process player card rates
        if player_data:
            for player in player_data:
                player_id = player.get("player_id")
                yellows = player.get("yellow_cards", 0)
                reds = player.get("red_cards", 0)
                minutes = player.get("minutes_played", 1)
                if player_id and minutes > 0:
                    self.player_card_rates[player_id] = (yellows + reds * 2) * 90 / minutes

    def predict_match(
        self,
        home_team_id: int,
        away_team_id: int,
        referee_id: Optional[int] = None,
        importance: float = 1.0,
        rivalry: bool = False,
        home_lineup: Optional[List[int]] = None,
        away_lineup: Optional[List[int]] = None,
    ) -> CardsPrediction:
        """Predict with player lineup adjustments."""
        base_pred = super().predict_match(home_team_id, away_team_id, referee_id, importance, rivalry)

        # Adjust for aggressive players in lineup
        if home_lineup:
            agg_factor = self._calculate_aggression_factor(home_lineup)
            base_pred.home_cards_mean *= agg_factor

        if away_lineup:
            agg_factor = self._calculate_aggression_factor(away_lineup)
            base_pred.away_cards_mean *= agg_factor

        # Recalculate totals
        base_pred.total_cards_mean = (
            base_pred.home_cards_mean
            + base_pred.away_cards_mean
            + base_pred.red_card_prob_home
            + base_pred.red_card_prob_away
        )

        # Recalculate over/under
        over_under = {}
        for line in [3.5, 4.5, 5.5, 6.5]:
            over, under = self._calculate_over_under(base_pred.total_cards_mean, line)
            over_under[line] = (over, under)
        base_pred.over_under_probs = over_under

        return base_pred

    def _calculate_aggression_factor(self, lineup: List[int]) -> float:
        """Calculate aggression factor from player card rates."""
        if not lineup:
            return 1.0

        rates = [self.player_card_rates.get(pid, 0.2) for pid in lineup]
        avg_rate = np.mean(rates)
        # League average ~0.2 cards per 90
        return 0.8 + avg_rate / 0.2 * 0.4  # 0.8 to 1.6 range