"""Tests for value betting engine."""
import pytest
from datetime import datetime
from backend.value_betting.engine import (
    ValueBettingEngine, OddsData, ModelProbabilities, BetSelection, ArbitrageDetector
)


class TestValueBettingEngine:
    """Tests for ValueBettingEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ValueBettingEngine()
        self.engine.min_edge = 0.02
        self.engine.min_ev = 0.05
        self.engine.max_kelly = 0.25

    def test_implied_probabilities_1x2(self):
        """Test implied probability calculation for 1X2."""
        # Fair odds: home 2.0, draw 3.2, away 3.6
        # Implied: 0.5, 0.3125, 0.2778 = 1.0903 (9% margin)
        imp_h, imp_d, imp_a = self.engine.calculate_implied_probabilities(2.0, 3.2, 3.6)

        assert imp_h is not None
        assert imp_d is not None
        assert imp_a is not None

        # After margin removal, should sum to ~1
        total = imp_h + imp_d + imp_a
        assert abs(total - 1.0) < 0.01

    def test_implied_probabilities_over_under(self):
        """Test implied probability for over/under."""
        imp_o, imp_u = self.engine.calculate_implied_over_under(1.9, 1.9)

        assert imp_o is not None
        assert imp_u is not None
        total = imp_o + imp_u
        assert abs(total - 1.0) < 0.01

    def test_implied_probabilities_btts(self):
        """Test implied probability for BTTS."""
        imp_y, imp_n = self.engine.calculate_implied_btts(1.8, 2.0)

        assert imp_y is not None
        assert imp_n is not None
        total = imp_y + imp_n
        assert abs(total - 1.0) < 0.01

    def test_kelly_stake(self):
        """Test Kelly criterion stake calculation."""
        # 60% probability at 2.0 odds
        kelly = self.engine.calculate_kelly_stake(0.6, 2.0)
        # b=1, p=0.6, q=0.4 -> (1*0.6 - 0.4)/1 = 0.2
        assert abs(kelly - 0.2) < 0.01

        # With fractional kelly
        fractional = self.engine.calculate_kelly_stake(0.6, 2.0, fraction=0.5)
        assert abs(fractional - 0.1) < 0.01

        # Negative edge
        kelly_neg = self.engine.calculate_kelly_stake(0.4, 2.0)
        assert kelly_neg == 0

    def test_evaluate_match_winner(self):
        """Test match winner evaluation."""
        odds = OddsData(
            market_type="match_winner",
            market_line=None,
            bookmaker_id=1,
            bookmaker_name="TestBookie",
            odd_home=2.2,
            odd_draw=3.3,
            odd_away=3.5,
            odd_over=None,
            odd_under=None,
            odd_btts_yes=None,
            odd_btts_no=None,
            odd_handicap=None,
            timestamp=datetime.utcnow(),
        )

        model_probs = ModelProbabilities(
            fixture_id=1,
            model_version="test",
            prob_home=0.5,
            prob_draw=0.25,
            prob_away=0.25,
            prob_over={},
            prob_under={},
            prob_btts_yes=0.5,
            prob_btts_no=0.5,
            prob_over_corners={},
            prob_over_cards={},
            confidence=0.7,
            data_quality=0.8,
        )

        bets = self.engine.evaluate_match_winner(odds, model_probs)

        # With 50% prob at 2.2 odds: edge = 0.5 - 0.42 = 0.08, EV = 0.5*2.2 - 1 = 0.1
        assert len(bets) >= 1
        home_bet = next((b for b in bets if b.selection == BetSelection.HOME), None)
        assert home_bet is not None
        assert home_bet.edge > 0.02
        assert home_bet.expected_value > 0.05

    def test_evaluate_over_under(self):
        """Test over/under evaluation."""
        odds = OddsData(
            market_type="over_under",
            market_line="2.5",
            bookmaker_id=1,
            bookmaker_name="TestBookie",
            odd_home=None,
            odd_draw=None,
            odd_away=None,
            odd_over=1.95,
            odd_under=1.85,
            odd_btts_yes=None,
            odd_btts_no=None,
            odd_handicap=None,
            timestamp=datetime.utcnow(),
        )

        model_probs = ModelProbabilities(
            fixture_id=1,
            model_version="test",
            prob_home=0.45,
            prob_draw=0.28,
            prob_away=0.27,
            prob_over={2.5: 0.55},
            prob_under={2.5: 0.45},
            prob_btts_yes=0.5,
            prob_btts_no=0.5,
            prob_over_corners={},
            prob_over_cards={},
            confidence=0.7,
            data_quality=0.8,
        )

        bets = self.engine.evaluate_over_under(odds, model_probs)

        assert len(bets) >= 1
        over_bet = next((b for b in bets if b.selection == BetSelection.OVER), None)
        assert over_bet is not None
        assert over_bet.market_line == "2.5"

    def test_find_all_value_bets(self):
        """Test finding all value bets."""
        odds_list = [
            OddsData(
                market_type="match_winner",
                market_line=None,
                bookmaker_id=1,
                bookmaker_name="Bookie1",
                odd_home=2.2, odd_draw=3.3, odd_away=3.5,
                odd_over=None, odd_under=None,
                odd_btts_yes=None, odd_btts_no=None,
                odd_handicap=None,
                timestamp=datetime.utcnow(),
            ),
            OddsData(
                market_type="over_under",
                market_line="2.5",
                bookmaker_id=1,
                bookmaker_name="Bookie1",
                odd_home=None, odd_draw=None, odd_away=None,
                odd_over=1.95, odd_under=1.85,
                odd_btts_yes=None, odd_btts_no=None,
                odd_handicap=None,
                timestamp=datetime.utcnow(),
            ),
        ]

        model_probs = ModelProbabilities(
            fixture_id=1,
            model_version="test",
            prob_home=0.5, prob_draw=0.25, prob_away=0.25,
            prob_over={2.5: 0.55}, prob_under={2.5: 0.45},
            prob_btts_yes=0.5, prob_btts_no=0.5,
            prob_over_corners={}, prob_over_cards={},
            confidence=0.7, data_quality=0.8,
        )

        bets = self.engine.find_all_value_bets(odds_list, model_probs)

        # Should be sorted by EV descending
        if len(bets) > 1:
            for i in range(len(bets) - 1):
                assert bets[i].expected_value >= bets[i + 1].expected_value


class TestArbitrageDetector:
    """Tests for arbitrage detection."""

    def test_find_arbitrage_1x2(self):
        """Test arbitrage detection for 1X2."""
        detector = ArbitrageDetector(min_profit_percent=0.5)

        odds_by_bookmaker = {
            1: OddsData(
                market_type="match_winner",
                market_line=None,
                bookmaker_id=1,
                bookmaker_name="Bookie1",
                odd_home=2.2, odd_draw=3.4, odd_away=3.6,
                odd_over=None, odd_under=None,
                odd_btts_yes=None, odd_btts_no=None,
                odd_handicap=None,
                timestamp=datetime.utcnow(),
            ),
            2: OddsData(
                market_type="match_winner",
                market_line=None,
                bookmaker_id=2,
                bookmaker_name="Bookie2",
                odd_home=2.1, odd_draw=3.5, odd_away=3.8,
                odd_over=None, odd_under=None,
                odd_btts_yes=None, odd_btts_no=None,
                odd_handicap=None,
                timestamp=datetime.utcnow(),
            ),
        }

        arbs = detector.find_arbitrage(odds_by_bookmaker, "match_winner")

        # Best combination: home 2.2, draw 3.5, away 3.8
        # Implied: 0.4545 + 0.2857 + 0.2632 = 1.0034 (no arb)
        # Need better odds for arbitrage

        # Test with clear arbitrage
        odds_by_bookmaker[1].odd_home = 3.0
        odds_by_bookmaker[1].odd_draw = 3.5
        odds_by_bookmaker[1].odd_away = 3.5
        # Implied: 0.333 + 0.286 + 0.286 = 0.905 (9.5% profit)

        arbs = detector.find_arbitrage(odds_by_bookmaker, "match_winner")
        assert len(arbs) >= 1
        assert arbs[0]["profit_percent"] > 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])