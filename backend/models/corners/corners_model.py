"""Corner prediction models."""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import poisson, nbinom


@dataclass
class CornerPrediction:
    """Corner prediction result."""
    home_corners_mean: float
    away_corners_mean: float
    total_corners_mean: float
    over_under_probs: Dict[float, Tuple[float, float]]
    handicap_probs: Dict[float, Tuple[float, float]]  # line -> (home, away)


class CornersModel:
    """Poisson/Negative Binomial model for corner prediction."""

    def __init__(self, max_corners: int = 20):
        self.max_corners = max_corners
        self.team_corner_stats: Dict[int, Dict] = {}
        self.league_avg_home_corners: float = 5.5
        self.league_avg_away_corners: float = 4.8
        self.use_negative_binomial: bool = True

    def fit(self, fixtures: List[Dict], team_ids: List[int]):
        """Fit corner model from historical fixtures."""
        # Initialize team stats
        for team_id in team_ids:
            self.team_corner_stats[team_id] = {
                "home_corners_for": [],
                "home_corners_against": [],
                "away_corners_for": [],
                "away_corners_against": [],
            }

        # Collect corner data
        for f in fixtures:
            home_id = f.get("home_team_id")
            away_id = f.get("away_team_id")
            home_corners = f.get("home_corners", 0)
            away_corners = f.get("away_corners", 0)

            if home_id in self.team_corner_stats:
                self.team_corner_stats[home_id]["home_corners_for"].append(home_corners)
                self.team_corner_stats[home_id]["home_corners_against"].append(away_corners)

            if away_id in self.team_corner_stats:
                self.team_corner_stats[away_id]["away_corners_for"].append(away_corners)
                self.team_corner_stats[away_id]["away_corners_against"].append(home_corners)

        # Calculate averages
        for team_id, stats in self.team_corner_stats.items():
            stats["avg_home_for"] = np.mean(stats["home_corners_for"]) if stats["home_corners_for"] else self.league_avg_home_corners
            stats["avg_home_against"] = np.mean(stats["home_corners_against"]) if stats["home_corners_against"] else self.league_avg_away_corners
            stats["avg_away_for"] = np.mean(stats["away_corners_for"]) if stats["away_corners_for"] else self.league_avg_away_corners
            stats["avg_away_against"] = np.mean(stats["away_corners_against"]) if stats["away_corners_against"] else self.league_avg_home_corners

            # Variance for negative binomial
            stats["var_home_for"] = np.var(stats["home_corners_for"]) if len(stats["home_corners_for"]) > 1 else stats["avg_home_for"]
            stats["var_away_for"] = np.var(stats["away_corners_for"]) if len(stats["away_corners_for"]) > 1 else stats["avg_away_for"]

    def predict_match(self, home_team_id: int, away_team_id: int) -> CornerPrediction:
        """Predict corners for a match."""
        home_stats = self.team_corner_stats.get(home_team_id, {})
        away_stats = self.team_corner_stats.get(away_team_id, {})

        # Expected corners using average of team's attack and opponent's defense
        home_corners_mean = (
            home_stats.get("avg_home_for", self.league_avg_home_corners) * 0.6
            + away_stats.get("avg_away_against", self.league_avg_home_corners) * 0.4
        )
        away_corners_mean = (
            away_stats.get("avg_away_for", self.league_avg_away_corners) * 0.6
            + home_stats.get("avg_home_against", self.league_avg_away_corners) * 0.4
        )

        total_mean = home_corners_mean + away_corners_mean

        # Over/Under probabilities
        over_under = {}
        for line in [7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5]:
            over, under = self._calculate_over_under(total_mean, line)
            over_under[line] = (over, under)

        # Handicap probabilities
        handicap = {}
        for line in [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5]:
            home_prob, away_prob = self._calculate_handicap(home_corners_mean, away_corners_mean, line)
            handicap[line] = (home_prob, away_prob)

        return CornerPrediction(
            home_corners_mean=home_corners_mean,
            away_corners_mean=away_corners_mean,
            total_corners_mean=total_mean,
            over_under_probs=over_under,
            handicap_probs=handicap,
        )

    def _calculate_over_under(self, mean: float, line: float) -> Tuple[float, float]:
        """Calculate over/under probabilities."""
        if self.use_negative_binomial:
            # Estimate negative binomial parameters
            # For simplicity, use Poisson with overdispersion adjustment
            var = mean * 1.3  # Typical overdispersion for corners
            if var <= mean:
                var = mean + 0.1

            # Negative binomial parameters
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
        """Calculate Asian handicap probabilities for corners."""
        # Convolution of two Poisson/NB distributions
        home_probs = self._get_distribution(home_mean)
        away_probs = self._get_distribution(away_mean)

        home_win = 0.0
        away_win = 0.0

        for h_corners, h_prob in home_probs.items():
            for a_corners, a_prob in away_probs.items():
                diff = h_corners - a_corners + line
                prob = h_prob * a_prob
                if diff > 0:
                    home_win += prob
                elif diff < 0:
                    away_win += prob
                # Push (diff == 0) is split or ignored

        total = home_win + away_win
        if total > 0:
            home_win /= total
            away_win /= total

        return home_win, away_win

    def _get_distribution(self, mean: float) -> Dict[int, float]:
        """Get probability distribution for corners."""
        dist = {}
        if self.use_negative_binomial:
            var = mean * 1.3
            if var <= mean:
                var = mean + 0.1
            r = mean ** 2 / (var - mean)
            p = r / (r + mean)

            for k in range(self.max_corners + 1):
                dist[k] = nbinom.pmf(k, r, p)
        else:
            for k in range(self.max_corners + 1):
                dist[k] = poisson.pmf(k, mean)

        return dist


class CornersModelAdvanced(CornersModel):
    """Advanced corner model with additional features."""

    def __init__(self, max_corners: int = 20):
        super().__init__(max_corners)
        self.team_features: Dict[int, Dict] = {}

    def fit(self, fixtures: List[Dict], team_ids: List[int]):
        """Fit with additional features."""
        super().fit(fixtures, team_ids)

        # Extract additional features
        for team_id in team_ids:
            team_fixtures = [f for f in fixtures if f.get("home_team_id") == team_id or f.get("away_team_id") == team_id]

            # Playing style features
            shots_per_game = 0
            possession_avg = 0
            attacks_wide = 0
            count = 0

            for f in team_fixtures:
                is_home = f.get("home_team_id") == team_id
                stats_key = "home" if is_home else "away"

                # Would need fixture statistics for these
                # Placeholder for future integration
                pass

            self.team_features[team_id] = {
                "shots_per_game": shots_per_game / max(count, 1),
                "possession_avg": possession_avg / max(count, 1),
                "attacks_wide_ratio": attacks_wide / max(count, 1),
            }

    def predict_match(self, home_team_id: int, away_team_id: int) -> CornerPrediction:
        """Predict with advanced features."""
        # Get base prediction
        base_pred = super().predict_match(home_team_id, away_team_id)

        # Adjust based on features
        home_features = self.team_features.get(home_team_id, {})
        away_features = self.team_features.get(away_team_id, {})

        # Adjust for playing style
        home_style_factor = 1.0
        away_style_factor = 1.0

        if home_features.get("attacks_wide_ratio", 0) > 0.4:
            home_style_factor *= 1.1
        if away_features.get("attacks_wide_ratio", 0) > 0.4:
            away_style_factor *= 1.1

        if home_features.get("possession_avg", 50) > 55:
            home_style_factor *= 1.05
        if away_features.get("possession_avg", 50) > 55:
            away_style_factor *= 1.05

        adjusted_home_mean = base_pred.home_corners_mean * home_style_factor
        adjusted_away_mean = base_pred.away_corners_mean * away_style_factor
        adjusted_total = adjusted_home_mean + adjusted_away_mean

        # Recalculate over/under with adjusted means
        over_under = {}
        for line in [7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5]:
            over, under = self._calculate_over_under(adjusted_total, line)
            over_under[line] = (over, under)

        handicap = {}
        for line in [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5]:
            home_prob, away_prob = self._calculate_handicap(adjusted_home_mean, adjusted_away_mean, line)
            handicap[line] = (home_prob, away_prob)

        return CornerPrediction(
            home_corners_mean=adjusted_home_mean,
            away_corners_mean=adjusted_away_mean,
            total_corners_mean=adjusted_total,
            over_under_probs=over_under,
            handicap_probs=handicap,
        )