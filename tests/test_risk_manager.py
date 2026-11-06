"""Tests for risk management."""
import pytest
from datetime import datetime, timedelta
from backend.risk_manager.manager import (
    RiskManager, ExposureLimits, BetProposal, PortfolioState, RiskLevel,
    BankrollSimulator
)


class TestRiskManager:
    """Tests for RiskManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.limits = ExposureLimits(
            max_per_match=0.05,
            max_per_market=0.03,
            max_per_bookmaker=0.10,
            max_daily=0.20,
            max_weekly=0.50,
            max_drawdown=0.15,
            max_concurrent_bets=20,
        )
        self.manager = RiskManager(self.limits)
        self.manager.initialize_portfolio(bankroll=1000.0)

    def test_portfolio_initialization(self):
        """Test portfolio initialization."""
        assert self.manager.portfolio.bankroll == 1000.0
        assert self.manager.portfolio.initial_bankroll == 1000.0
        assert self.manager.portfolio.current_exposure == 0.0

    def test_update_portfolio(self):
        """Test portfolio update."""
        open_bets = [
            {"fixture_id": 1, "stake": 50, "market_type": "match_winner",
             "bookmaker_id": 1, "timestamp": datetime.utcnow().isoformat()},
            {"fixture_id": 2, "stake": 30, "market_type": "over_under",
             "bookmaker_id": 2, "timestamp": datetime.utcnow().isoformat()},
        ]
        self.manager.update_portfolio(bankroll=1050.0, open_bets=open_bets)

        assert self.manager.portfolio.bankroll == 1050.0
        assert self.manager.portfolio.current_exposure == 0.08  # 80/1000

    def test_assess_bet_approved(self):
        """Test bet approval within limits."""
        proposal = BetProposal(
            fixture_id=1,
            selection="home",
            market_type="match_winner",
            market_line=None,
            odd=2.0,
            stake=30.0,
            kelly_stake=40.0,
            model_prob=0.55,
            edge=0.05,
            ev=0.1,
            confidence=0.7,
            bookmaker_id=1,
            bookmaker_name="TestBookie",
        )

        assessment = self.manager.assess_bet(proposal)

        assert assessment.approved is True
        assert assessment.adjusted_stake == 30.0
        assert assessment.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]

    def test_assess_bet_exceeds_per_match_limit(self):
        """Test bet rejection for per-match limit."""
        # Add existing bet on same match
        self.manager.portfolio.open_bets = [
            {"fixture_id": 1, "stake": 40, "market_type": "match_winner",
             "bookmaker_id": 1, "timestamp": datetime.utcnow().isoformat()},
        ]
        self.manager._recalculate_exposures()

        # Try to add another 30 on same match (would be 70 total = 7% > 5%)
        proposal = BetProposal(
            fixture_id=1,
            selection="away",
            market_type="over_under",
            market_line="2.5",
            odd=2.0,
            stake=30.0,
            kelly_stake=40.0,
            model_prob=0.55,
            edge=0.05,
            ev=0.1,
            confidence=0.7,
            bookmaker_id=1,
            bookmaker_name="TestBookie",
        )

        assessment = self.manager.assess_bet(proposal)

        assert assessment.approved is True  # Should be approved with reduced stake
        assert assessment.adjusted_stake < 30.0  # Reduced to respect limit
        assert len(assessment.warnings) > 0

    def test_assess_bet_exceeds_daily_limit(self):
        """Test bet rejection for daily limit."""
        # Set high daily exposure
        self.manager.portfolio.daily_exposure = 0.18  # 18%

        proposal = BetProposal(
            fixture_id=1,
            selection="home",
            market_type="match_winner",
            market_line=None,
            odd=2.0,
            stake=50.0,
            kelly_stake=40.0,
            model_prob=0.55,
            edge=0.05,
            ev=0.1,
            confidence=0.7,
            bookmaker_id=1,
            bookmaker_name="TestBookie",
        )

        assessment = self.manager.assess_bet(proposal)

        # 50/1000 = 5%, would make daily 23% > 20%
        assert assessment.adjusted_stake < 50.0

    def test_assess_bet_drawdown_limit(self):
        """Test bet rejection when drawdown exceeded."""
        self.manager.portfolio.current_drawdown = 0.16  # 16% > 15% limit

        proposal = BetProposal(
            fixture_id=1,
            selection="home",
            market_type="match_winner",
            market_line=None,
            odd=2.0,
            stake=30.0,
            kelly_stake=40.0,
            model_prob=0.55,
            edge=0.05,
            ev=0.1,
            confidence=0.7,
            bookmaker_id=1,
            bookmaker_name="TestBookie",
        )

        assessment = self.manager.assess_bet(proposal)

        assert assessment.approved is False
        assert any("drawdown" in r.lower() for r in assessment.rejected_reasons)

    def test_assess_bet_concurrent_limit(self):
        """Test bet rejection for concurrent bets limit."""
        self.manager.portfolio.open_bets = [
            {"fixture_id": i, "stake": 10} for i in range(20)
        ]

        proposal = BetProposal(
            fixture_id=21,
            selection="home",
            market_type="match_winner",
            market_line=None,
            odd=2.0,
            stake=30.0,
            kelly_stake=40.0,
            model_prob=0.55,
            edge=0.05,
            ev=0.1,
            confidence=0.7,
            bookmaker_id=1,
            bookmaker_name="TestBookie",
        )

        assessment = self.manager.assess_bet(proposal)

        assert assessment.approved is False
        assert any("concurrent" in r.lower() for r in assessment.rejected_reasons)

    def test_get_recommended_stake(self):
        """Test recommended stake calculation."""
        stake = self.manager.get_recommended_stake(
            kelly_stake=50.0,
            confidence=0.8,
            edge=0.05,
        )
        # 50 * 0.8 * (0.05/0.05) = 40
        assert abs(stake - 40.0) < 1.0

        # Low confidence reduces stake
        stake_low_conf = self.manager.get_recommended_stake(
            kelly_stake=50.0,
            confidence=0.5,
            edge=0.05,
        )
        assert stake_low_conf < stake

        # Low edge reduces stake
        stake_low_edge = self.manager.get_recommended_stake(
            kelly_stake=50.0,
            confidence=0.8,
            edge=0.02,
        )
        assert stake_low_edge < stake


class TestBankrollSimulator:
    """Tests for BankrollSimulator."""

    def test_simulate_flat(self):
        """Test flat stake simulation."""
        simulator = BankrollSimulator(initial_bankroll=1000.0)

        bets = [
            {"model_prob": 0.55, "odd": 2.0, "edge": 0.05, "ev": 0.1} for _ in range(20)
        ]

        result = simulator.simulate(bets, strategy="flat")

        assert "final_bankroll" in result
        assert "roi_percent" in result
        assert "total_bets" in result
        assert result["total_bets"] == 20

    def test_simulate_fractional_kelly(self):
        """Test fractional Kelly simulation."""
        simulator = BankrollSimulator(initial_bankroll=1000.0)

        bets = [
            {"model_prob": 0.55, "odd": 2.0, "edge": 0.05, "ev": 0.1} for _ in range(20)
        ]

        result = simulator.simulate(bets, strategy="fractional_kelly", kelly_fraction=0.25)

        assert "final_bankroll" in result
        assert result["max_drawdown_percent"] >= 0

    def test_monte_carlo(self):
        """Test Monte Carlo simulation."""
        simulator = BankrollSimulator(initial_bankroll=1000.0)

        bets = [
            {"model_prob": 0.55, "odd": 2.0, "edge": 0.05, "ev": 0.1} for _ in range(10)
        ]

        result = simulator.run_monte_carlo(bets, simulations=50, strategy="fractional_kelly")

        assert result["simulations"] == 50
        assert "mean_final_bankroll" in result
        assert "prob_profit" in result
        assert "prob_ruin" in result
        assert 0 <= result["prob_profit"] <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])