"""Tests for statistical models."""
import pytest
import math
from backend.models.goals.poisson_model import (
    PoissonModel, DixonColesModel, EloModel, CombinedGoalsModel, MatchPrediction
)
from backend.models.corners.corners_model import CornersModel, CornerPrediction
from backend.models.cards.cards_model import CardsModel, CardsPrediction
from backend.models.live.live_model import LiveModel, LiveMatchState, MatchState


class TestPoissonModel:
    """Tests for Poisson goal model."""

    def test_fit_and_predict(self):
        """Test model fitting and prediction."""
        model = PoissonModel(max_goals=5)

        # Sample fixtures
        fixtures = [
            {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1, "date": "2024-01-01"},
            {"home_team_id": 2, "away_team_id": 1, "home_goals": 1, "away_goals": 2, "date": "2024-01-08"},
            {"home_team_id": 1, "away_team_id": 3, "home_goals": 3, "away_goals": 0, "date": "2024-01-15"},
            {"home_team_id": 3, "away_team_id": 1, "home_goals": 0, "away_goals": 1, "date": "2024-01-22"},
            {"home_team_id": 2, "away_team_id": 3, "home_goals": 2, "away_goals": 2, "date": "2024-01-29"},
            {"home_team_id": 3, "away_team_id": 2, "home_goals": 1, "away_goals": 1, "date": "2024-02-05"},
        ]

        model.fit(fixtures, [1, 2, 3])

        # Check team strengths were calculated
        assert 1 in model.team_strengths
        assert 2 in model.team_strengths
        assert 3 in model.team_strengths

        # Predict a match
        pred = model.predict_match(1, 2)

        assert isinstance(pred, MatchPrediction)
        assert 0 <= pred.home_win_prob <= 1
        assert 0 <= pred.draw_prob <= 1
        assert 0 <= pred.away_win_prob <= 1
        assert abs(pred.home_win_prob + pred.draw_prob + pred.away_win_prob - 1.0) < 0.01

        # Check over/under probabilities
        for line, (over, under) in pred.over_under_probs.items():
            assert 0 <= over <= 1
            assert 0 <= under <= 1
            assert abs(over + under - 1.0) < 0.01

        # Check BTTS
        assert 0 <= pred.btts_probs[0] <= 1
        assert 0 <= pred.btts_probs[1] <= 1
        assert abs(pred.btts_probs[0] + pred.btts_probs[1] - 1.0) < 0.01

        # Check correct scores sum to ~1
        total_score_prob = sum(pred.correct_score_probs.values())
        assert abs(total_score_prob - 1.0) < 0.01

    def test_expected_goals_positive(self):
        """Test that expected goals are positive."""
        model = PoissonModel()
        fixtures = [
            {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
            {"home_team_id": 2, "away_team_id": 1, "home_goals": 1, "away_goals": 2},
        ]
        model.fit(fixtures, [1, 2])
        pred = model.predict_match(1, 2)

        assert pred.expected_goals_home > 0
        assert pred.expected_goals_away > 0


class TestDixonColesModel:
    """Tests for Dixon-Coles model."""

    def test_dixon_coles_adjustment(self):
        """Test Dixon-Coles adjustment factor."""
        model = DixonColesModel(rho=0.1)

        # Test various score combinations
        adj_00 = model._dixon_coles_adjustment(0, 0, 1.5, 1.2)
        adj_01 = model._dixon_coles_adjustment(0, 1, 1.5, 1.2)
        adj_10 = model._dixon_coles_adjustment(1, 0, 1.5, 1.2)
        adj_11 = model._dixon_coles_adjustment(1, 1, 1.5, 1.2)
        adj_22 = model._dixon_coles_adjustment(2, 2, 1.5, 1.2)

        # 0-0 should be reduced
        assert adj_00 < 1.0
        # 0-1 and 1-0 should be increased
        assert adj_01 > 1.0
        assert adj_10 > 1.0
        # 1-1 should be reduced
        assert adj_11 < 1.0
        # Higher scores unchanged
        assert adj_22 == 1.0

    def test_predict_normalized(self):
        """Test that probabilities are normalized after adjustment."""
        model = DixonColesModel(rho=0.1)
        fixtures = [
            {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1},
            {"home_team_id": 2, "away_team_id": 1, "home_goals": 1, "away_goals": 2},
            {"home_team_id": 1, "away_team_id": 3, "home_goals": 0, "away_goals": 0},
            {"home_team_id": 3, "away_team_id": 1, "home_goals": 0, "away_goals": 0},
        ]
        model.fit(fixtures, [1, 2, 3])
        pred = model.predict_match(1, 2)

        total = pred.home_win_prob + pred.draw_prob + pred.away_win_prob
        assert abs(total - 1.0) < 0.01


class TestEloModel:
    """Tests for Elo rating model."""

    def test_elo_updates(self):
        """Test Elo rating updates."""
        elo = EloModel(k_factor=20, home_advantage=100)

        # Initial ratings
        assert elo.get_rating(1) == 1500
        assert elo.get_rating(2) == 1500

        # Home wins
        elo.update_ratings(1, 2, 2, 1)

        # Home rating should increase, away decrease
        assert elo.get_rating(1) > 1500
        assert elo.get_rating(2) < 1500

        # Draw
        elo.update_ratings(1, 2, 1, 1)

        # Away wins
        elo.update_ratings(1, 2, 0, 2)
        assert elo.get_rating(1) < 1500
        assert elo.get_rating(2) > 1500

    def test_expected_score(self):
        """Test expected score calculation."""
        elo = EloModel()

        # Equal ratings
        exp = elo.expected_score(1500, 1500)
        assert abs(exp - 0.5) < 0.01

        # 400 point difference
        exp = elo.expected_score(1900, 1500)
        assert abs(exp - 0.91) < 0.02

    def test_fit_and_predict(self):
        """Test fitting from fixtures and prediction."""
        elo = EloModel()
        fixtures = [
            {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1, "date": "2024-01-01"},
            {"home_team_id": 2, "away_team_id": 1, "home_goals": 1, "away_goals": 2, "date": "2024-01-08"},
            {"home_team_id": 1, "away_team_id": 3, "home_goals": 3, "away_goals": 0, "date": "2024-01-15"},
        ]
        elo.fit(fixtures)

        home_win, draw, away_win = elo.predict_match(1, 2)

        assert 0 <= home_win <= 1
        assert 0 <= draw <= 1
        assert 0 <= away_win <= 1
        assert abs(home_win + draw + away_win - 1.0) < 0.01


class TestCombinedGoalsModel:
    """Tests for combined goals model."""

    def test_combined_prediction(self):
        """Test combined model prediction."""
        model = CombinedGoalsModel()
        fixtures = [
            {"home_team_id": 1, "away_team_id": 2, "home_goals": 2, "away_goals": 1, "date": "2024-01-01"},
            {"home_team_id": 2, "away_team_id": 1, "home_goals": 1, "away_goals": 2, "date": "2024-01-08"},
            {"home_team_id": 1, "away_team_id": 3, "home_goals": 3, "away_goals": 0, "date": "2024-01-15"},
            {"home_team_id": 3, "away_team_id": 1, "home_goals": 0, "away_goals": 1, "date": "2024-01-22"},
        ]
        model.fit(fixtures, [1, 2, 3])
        pred = model.predict_match(1, 2)

        assert isinstance(pred, MatchPrediction)
        assert 0 <= pred.home_win_prob <= 1
        assert 0 <= pred.draw_prob <= 1
        assert 0 <= pred.away_win_prob <= 1


class TestCornersModel:
    """Tests for corners model."""

    def test_fit_and_predict(self):
        """Test corners model fitting and prediction."""
        model = CornersModel()
        fixtures = [
            {"home_team_id": 1, "away_team_id": 2, "home_corners": 6, "away_corners": 4},
            {"home_team_id": 2, "away_team_id": 1, "home_corners": 5, "away_corners": 3},
            {"home_team_id": 1, "away_team_id": 3, "home_corners": 8, "away_corners": 2},
            {"home_team_id": 3, "away_team_id": 1, "home_corners": 3, "away_corners": 7},
        ]
        model.fit(fixtures, [1, 2, 3])
        pred = model.predict_match(1, 2)

        assert isinstance(pred, CornerPrediction)
        assert pred.home_corners_mean > 0
        assert pred.away_corners_mean > 0
        assert pred.total_corners_mean > 0

        # Check over/under
        for line, (over, under) in pred.over_under_probs.items():
            assert 0 <= over <= 1
            assert 0 <= under <= 1

        # Check handicap
        for line, (home, away) in pred.handicap_probs.items():
            assert 0 <= home <= 1
            assert 0 <= away <= 1


class TestCardsModel:
    """Tests for cards model."""

    def test_fit_and_predict(self):
        """Test cards model fitting and prediction."""
        model = CardsModel()
        fixtures = [
            {"home_team_id": 1, "away_team_id": 2, "home_yellow_cards": 2, "away_yellow_cards": 3, "home_red_cards": 0, "away_red_cards": 0},
            {"home_team_id": 2, "away_team_id": 1, "home_yellow_cards": 1, "away_yellow_cards": 2, "home_red_cards": 0, "away_red_cards": 1},
            {"home_team_id": 1, "away_team_id": 3, "home_yellow_cards": 3, "away_yellow_cards": 1, "home_red_cards": 0, "away_red_cards": 0},
        ]
        model.fit(fixtures, [1, 2, 3])
        pred = model.predict_match(1, 2, referee_id=None)

        assert isinstance(pred, CardsPrediction)
        assert pred.home_cards_mean >= 0
        assert pred.away_cards_mean >= 0
        assert 0 <= pred.red_card_prob_home <= 1
        assert 0 <= pred.red_card_prob_away <= 1

    def test_referee_adjustment(self):
        """Test referee influence on cards."""
        model = CardsModel()
        fixtures = [
            {"home_team_id": 1, "away_team_id": 2, "home_yellow_cards": 2, "away_yellow_cards": 2},
        ]
        model.fit(fixtures, [1, 2])

        # Strict referee
        pred_strict = model.predict_match(1, 2, referee_id=1)
        referee_data = [{"id": 1, "yellow_cards_per_game": 6.0, "red_cards_per_game": 0.3}]
        model.referee_stats[1] = {"yellow_per_game": 6.0, "red_per_game": 0.3, "home_bias": 0}

        pred_strict = model.predict_match(1, 2, referee_id=1)

        # Lenient referee
        model.referee_stats[2] = {"yellow_per_game": 3.0, "red_per_game": 0.1, "home_bias": 0}
        pred_lenient = model.predict_match(1, 2, referee_id=2)

        # Strict referee should predict more cards
        assert pred_strict.total_cards_mean > pred_lenient.total_cards_mean


class TestLiveModel:
    """Tests for live match model."""

    def test_live_state_creation(self):
        """Test creating live state from events."""
        events = [
            {"type": "Goal", "team_id": 1, "detail": "Normal Goal", "time_elapsed": 23},
            {"type": "Card", "team_id": 2, "detail": "Yellow Card", "time_elapsed": 35},
        ]
        statistics = [
            {"team_id": 1, "type": "Total Shots", "value": "10"},
            {"team_id": 2, "type": "Total Shots", "value": "5"},
            {"team_id": 1, "type": "Shots on Goal", "value": "4"},
            {"team_id": 2, "type": "Shots on Goal", "value": "2"},
            {"team_id": 1, "type": "Corner Kicks", "value": "5"},
            {"team_id": 2, "type": "Corner Kicks", "value": "2"},
        ]

        state = LiveMatchState(
            fixture_id=123,
            minute=40,
            added_time=2,
            state=MatchState.FIRST_HALF,
            home_score=1,
            away_score=0,
            home_shots=10,
            away_shots=5,
            home_shots_on_target=4,
            away_shots_on_target=2,
            home_corners=5,
            away_corners=2,
        )

        assert state.minute == 40
        assert state.home_score == 1
        assert state.state == MatchState.FIRST_HALF

    def test_live_update(self):
        """Test live prediction update."""
        model = LiveModel()
        model.initialize_from_pre_match(0.45, 0.28, 0.27, 1.5, 1.2)

        state = LiveMatchState(
            fixture_id=123,
            minute=60,
            added_time=0,
            state=MatchState.SECOND_HALF,
            home_score=1,
            away_score=0,
            home_xg=1.2,
            away_xg=0.5,
        )

        pred = model.update(state)

        assert 0 <= pred.home_win_prob <= 1
        assert 0 <= pred.draw_prob <= 1
        assert 0 <= pred.away_win_prob <= 1
        assert pred.total_goals_expected >= 1  # At least current goals

        # Next goal probabilities
        assert "home" in pred.next_goal_probability
        assert "away" in pred.next_goal_probability
        assert "none" in pred.next_goal_probability


if __name__ == "__main__":
    pytest.main([__file__, "-v"])