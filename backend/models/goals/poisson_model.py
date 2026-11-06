"""Poisson-based goal prediction models with Dixon-Coles adjustment."""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson


@dataclass
class TeamStrength:
    """Team attacking and defensive strength parameters."""
    attack: float
    defense: float
    home_attack: float = 0.0
    home_defense: float = 0.0
    away_attack: float = 0.0
    away_defense: float = 0.0


@dataclass
class MatchPrediction:
    """Prediction result for a match."""
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    over_under_probs: Dict[float, Tuple[float, float]]  # line -> (over, under)
    btts_probs: Tuple[float, float]  # (yes, no)
    correct_score_probs: Dict[Tuple[int, int], float]  # (home, away) -> prob
    expected_goals_home: float
    expected_goals_away: float


class PoissonModel:
    """Basic Poisson model for goal prediction."""

    def __init__(self, max_goals: int = 10):
        self.max_goals = max_goals
        self.team_strengths: Dict[int, TeamStrength] = {}
        self.league_avg_home_goals: float = 1.4
        self.league_avg_away_goals: float = 1.1
        self.home_advantage: float = 0.3

    def fit(
        self,
        fixtures: List[Dict],
        team_ids: List[int],
        league_avg_home: float = None,
        league_avg_away: float = None,
    ):
        """Fit model parameters from historical fixtures."""
        if league_avg_home:
            self.league_avg_home_goals = league_avg_home
        if league_avg_away:
            self.league_avg_away_goals = league_avg_away

        # Initialize team strengths
        for team_id in team_ids:
            self.team_strengths[team_id] = TeamStrength(
                attack=1.0,
                defense=1.0,
            )

        # Simple iterative fitting (like Dixon-Coles original)
        self._fit_attack_defense(fixtures)

    def _fit_attack_defense(self, fixtures: List[Dict]):
        """Fit attack and defense parameters using maximum likelihood."""
        # Group fixtures by team
        team_fixtures = {}
        for f in fixtures:
            home_id = f.get("home_team_id")
            away_id = f.get("away_team_id")
            home_goals = f.get("home_goals", 0)
            away_goals = f.get("away_goals", 0)

            if home_id not in team_fixtures:
                team_fixtures[home_id] = {"home": [], "away": []}
            if away_id not in team_fixtures:
                team_fixtures[away_id] = {"home": [], "away": []}

            team_fixtures[home_id]["home"].append((home_goals, away_goals, away_id))
            team_fixtures[away_id]["away"].append((away_goals, home_goals, home_id))

        # Iterative scaling
        for _ in range(100):
            max_change = 0.0

            for team_id, data in team_fixtures.items():
                if team_id not in self.team_strengths:
                    continue

                strength = self.team_strengths[team_id]

                # Home attack
                home_goals_scored = sum(g[0] for g in data["home"])
                home_expected = sum(
                    strength.attack * self.team_strengths.get(opp_id, TeamStrength(1, 1)).defense * self.league_avg_home_goals
                    for _, _, opp_id in data["home"]
                )
                if home_expected > 0 and len(data["home"]) > 0:
                    new_attack = home_goals_scored / home_expected
                    max_change = max(max_change, abs(new_attack - strength.attack))
                    strength.attack = new_attack

                # Away attack
                away_goals_scored = sum(g[0] for g in data["away"])
                away_expected = sum(
                    strength.attack * self.team_strengths.get(opp_id, TeamStrength(1, 1)).defense * self.league_avg_away_goals
                    for _, _, opp_id in data["away"]
                )
                if away_expected > 0 and len(data["away"]) > 0:
                    new_attack = away_goals_scored / away_expected
                    max_change = max(max_change, abs(new_attack - strength.attack))
                    strength.attack = new_attack

                # Home defense
                home_goals_conceded = sum(g[1] for g in data["home"])
                home_expected_conceded = sum(
                    self.team_strengths.get(opp_id, TeamStrength(1, 1)).attack * strength.defense * self.league_avg_away_goals
                    for _, _, opp_id in data["home"]
                )
                if home_expected_conceded > 0 and len(data["home"]) > 0:
                    new_defense = home_goals_conceded / home_expected_conceded
                    max_change = max(max_change, abs(new_defense - strength.defense))
                    strength.defense = new_defense

                # Away defense
                away_goals_conceded = sum(g[1] for g in data["away"])
                away_expected_conceded = sum(
                    self.team_strengths.get(opp_id, TeamStrength(1, 1)).attack * strength.defense * self.league_avg_home_goals
                    for _, _, opp_id in data["away"]
                )
                if away_expected_conceded > 0 and len(data["away"]) > 0:
                    new_defense = away_goals_conceded / away_expected_conceded
                    max_change = max(max_change, abs(new_defense - strength.defense))
                    strength.defense = new_defense

            if max_change < 0.001:
                break

    def predict_match(self, home_team_id: int, away_team_id: int) -> MatchPrediction:
        """Predict match outcome probabilities."""
        home_strength = self.team_strengths.get(home_team_id, TeamStrength(1.0, 1.0))
        away_strength = self.team_strengths.get(away_team_id, TeamStrength(1.0, 1.0))

        # Expected goals
        lambda_home = (
            home_strength.attack
            * away_strength.defense
            * self.league_avg_home_goals
            * math.exp(self.home_advantage)
        )
        lambda_away = (
            away_strength.attack
            * home_strength.defense
            * self.league_avg_away_goals
            * math.exp(-self.home_advantage)
        )

        return self._calculate_probabilities(lambda_home, lambda_away)

    def _calculate_probabilities(
        self, lambda_home: float, lambda_away: float
    ) -> MatchPrediction:
        """Calculate all probabilities from expected goals."""
        # Score matrix
        score_probs = {}
        home_win = draw = away_win = 0.0

        for h in range(self.max_goals + 1):
            for a in range(self.max_goals + 1):
                prob = poisson.pmf(h, lambda_home) * poisson.pmf(a, lambda_away)
                score_probs[(h, a)] = prob

                if h > a:
                    home_win += prob
                elif h == a:
                    draw += prob
                else:
                    away_win += prob

        # Over/Under probabilities
        over_under = {}
        for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            over = under = 0.0
            for (h, a), prob in score_probs.items():
                total = h + a
                if total > line:
                    over += prob
                else:
                    under += prob
            over_under[line] = (over, under)

        # Both Teams To Score
        btts_yes = sum(
            prob for (h, a), prob in score_probs.items() if h > 0 and a > 0
        )
        btts_no = 1.0 - btts_yes

        return MatchPrediction(
            home_win_prob=home_win,
            draw_prob=draw,
            away_win_prob=away_win,
            over_under_probs=over_under,
            btts_probs=(btts_yes, btts_no),
            correct_score_probs=score_probs,
            expected_goals_home=lambda_home,
            expected_goals_away=lambda_away,
        )


class DixonColesModel(PoissonModel):
    """Dixon-Coles model with adjustment for low-scoring draws."""

    def __init__(self, max_goals: int = 10, rho: float = 0.1):
        super().__init__(max_goals)
        self.rho = rho  # Dependency parameter for 0-0, 0-1, 1-0, 1-1

    def _dixon_coles_adjustment(self, h: int, a: int, lambda_home: float, lambda_away: float) -> float:
        """Calculate Dixon-Coles adjustment factor."""
        if h == 0 and a == 0:
            return 1 - lambda_home * lambda_away * self.rho
        elif h == 0 and a == 1:
            return 1 + lambda_home * self.rho
        elif h == 1 and a == 0:
            return 1 + lambda_away * self.rho
        elif h == 1 and a == 1:
            return 1 - self.rho
        return 1.0

    def _calculate_probabilities(
        self, lambda_home: float, lambda_away: float
    ) -> MatchPrediction:
        """Calculate probabilities with Dixon-Coles adjustment."""
        score_probs = {}
        home_win = draw = away_win = 0.0

        for h in range(self.max_goals + 1):
            for a in range(self.max_goals + 1):
                base_prob = poisson.pmf(h, lambda_home) * poisson.pmf(a, lambda_away)
                adjustment = self._dixon_coles_adjustment(h, a, lambda_home, lambda_away)
                prob = base_prob * adjustment
                score_probs[(h, a)] = prob

                if h > a:
                    home_win += prob
                elif h == a:
                    draw += prob
                else:
                    away_win += prob

        # Normalize (adjustment can cause sum != 1)
        total = sum(score_probs.values())
        if total > 0:
            for key in score_probs:
                score_probs[key] /= total
            home_win /= total
            draw /= total
            away_win /= total

        # Over/Under
        over_under = {}
        for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            over = under = 0.0
            for (h, a), prob in score_probs.items():
                total_goals = h + a
                if total_goals > line:
                    over += prob
                else:
                    under += prob
            over_under[line] = (over, under)

        # BTTS
        btts_yes = sum(
            prob for (h, a), prob in score_probs.items() if h > 0 and a > 0
        )
        btts_no = 1.0 - btts_yes

        return MatchPrediction(
            home_win_prob=home_win,
            draw_prob=draw,
            away_win_prob=away_win,
            over_under_probs=over_under,
            btts_probs=(btts_yes, btts_no),
            correct_score_probs=score_probs,
            expected_goals_home=lambda_home,
            expected_goals_away=lambda_away,
        )

    def estimate_rho(self, fixtures: List[Dict]) -> float:
        """Estimate rho parameter from historical data."""
        # Count low-scoring draws
        counts = {0: 0, 1: 0}
        total = 0

        for f in fixtures:
            h = f.get("home_goals", 0)
            a = f.get("away_goals", 0)
            if h <= 1 and a <= 1:
                total += 1
                if h == 0 and a == 0:
                    counts[0] += 1
                elif (h == 0 and a == 1) or (h == 1 and a == 0):
                    counts[1] += 1

        if total == 0:
            return 0.1

        # Simple moment estimator
        observed_00 = counts[0] / total
        observed_01 = counts[1] / total

        # Expected under independence (approximate)
        # This is a simplified estimation
        return min(0.5, max(-0.5, observed_00 - observed_01))


class EloModel:
    """Elo rating model for team strength."""

    def __init__(self, k_factor: float = 20.0, home_advantage: float = 100.0):
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.ratings: Dict[int, float] = {}
        self.default_rating = 1500.0

    def get_rating(self, team_id: int) -> float:
        """Get team's current Elo rating."""
        return self.ratings.get(team_id, self.default_rating)

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Calculate expected score for team A vs team B."""
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def update_ratings(
        self,
        home_team_id: int,
        away_team_id: int,
        home_goals: int,
        away_goals: int,
    ):
        """Update ratings after a match."""
        home_rating = self.get_rating(home_team_id)
        away_rating = self.get_rating(away_team_id)

        # Expected scores with home advantage
        home_expected = self.expected_score(home_rating + self.home_advantage, away_rating)
        away_expected = 1.0 - home_expected

        # Actual scores
        if home_goals > away_goals:
            home_actual = 1.0
            away_actual = 0.0
        elif home_goals == away_goals:
            home_actual = 0.5
            away_actual = 0.5
        else:
            home_actual = 0.0
            away_actual = 1.0

        # Update ratings
        self.ratings[home_team_id] = home_rating + self.k_factor * (home_actual - home_expected)
        self.ratings[away_team_id] = away_rating + self.k_factor * (away_actual - away_expected)

    def fit(self, fixtures: List[Dict]):
        """Fit Elo ratings from historical fixtures."""
        # Sort by date
        fixtures_sorted = sorted(fixtures, key=lambda x: x.get("date", ""))

        for f in fixtures_sorted:
            home_id = f.get("home_team_id")
            away_id = f.get("away_team_id")
            home_goals = f.get("home_goals", 0)
            away_goals = f.get("away_goals", 0)

            if home_id and away_id:
                self.update_ratings(home_id, away_id, home_goals, away_goals)

    def predict_match(self, home_team_id: int, away_team_id: int) -> Tuple[float, float, float]:
        """Predict match outcome probabilities from Elo."""
        home_rating = self.get_rating(home_team_id)
        away_rating = self.get_rating(away_team_id)

        home_expected = self.expected_score(home_rating + self.home_advantage, away_rating)
        away_expected = 1.0 - home_expected

        # Convert to win/draw/loss (simplified)
        # Draw probability approximated from expected score difference
        diff = abs(home_expected - away_expected)
        draw_prob = max(0.15, 0.35 - diff * 0.5)

        if home_expected > away_expected:
            home_win = home_expected * (1 - draw_prob) / (home_expected + away_expected * 0.5)
            away_win = 1.0 - home_win - draw_prob
        else:
            away_win = away_expected * (1 - draw_prob) / (away_expected + home_expected * 0.5)
            home_win = 1.0 - away_win - draw_prob

        return home_win, draw_prob, away_win


class CombinedGoalsModel:
    """Combined model using Poisson + Dixon-Coles + Elo."""

    def __init__(self, max_goals: int = 10):
        self.poisson = PoissonModel(max_goals)
        self.dixon_coles = DixonColesModel(max_goals)
        self.elo = EloModel()
        self.weights = {
            "poisson": 0.3,
            "dixon_coles": 0.5,
            "elo": 0.2,
        }

    def fit(self, fixtures: List[Dict], team_ids: List[int]):
        """Fit all sub-models."""
        self.poisson.fit(fixtures, team_ids)
        self.dixon_coles.fit(fixtures, team_ids)
        self.elo.fit(fixtures)

        # Estimate Dixon-Coles rho
        rho = self.dixon_coles.estimate_rho(fixtures)
        self.dixon_coles.rho = rho

    def predict_match(self, home_team_id: int, away_team_id: int) -> MatchPrediction:
        """Combine predictions from all models."""
        pred_poisson = self.poisson.predict_match(home_team_id, away_team_id)
        pred_dc = self.dixon_coles.predict_match(home_team_id, away_team_id)
        elo_home, elo_draw, elo_away = self.elo.predict_match(home_team_id, away_team_id)

        # Weighted combination
        w = self.weights
        home_win = (
            w["poisson"] * pred_poisson.home_win_prob
            + w["dixon_coles"] * pred_dc.home_win_prob
            + w["elo"] * elo_home
        )
        draw = (
            w["poisson"] * pred_poisson.draw_prob
            + w["dixon_coles"] * pred_dc.draw_prob
            + w["elo"] * elo_draw
        )
        away_win = (
            w["poisson"] * pred_poisson.away_win_prob
            + w["dixon_coles"] * pred_dc.away_win_prob
            + w["elo"] * elo_away
        )

        # Normalize
        total = home_win + draw + away_win
        home_win /= total
        draw /= total
        away_win /= total

        # Use Dixon-Coles for score-based markets (more accurate for low scores)
        return MatchPrediction(
            home_win_prob=home_win,
            draw_prob=draw,
            away_win_prob=away_win,
            over_under_probs=pred_dc.over_under_probs,
            btts_probs=pred_dc.btts_probs,
            correct_score_probs=pred_dc.correct_score_probs,
            expected_goals_home=pred_dc.expected_goals_home,
            expected_goals_away=pred_dc.expected_goals_away,
        )