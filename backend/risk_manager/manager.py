"""Risk management for betting operations."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from enum import Enum


class RiskLevel(Enum):
    """Risk level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ExposureLimits:
    """Exposure limits configuration."""
    max_per_match: float = 0.05       # 5% of bankroll per match
    max_per_market: float = 0.03      # 3% per market type
    max_per_bookmaker: float = 0.10   # 10% per bookmaker
    max_daily: float = 0.20           # 20% daily exposure
    max_weekly: float = 0.50          # 50% weekly exposure
    max_drawdown: float = 0.15        # 15% max drawdown
    max_concurrent_bets: int = 20     # Max simultaneous bets


@dataclass
class BetProposal:
    """Proposed bet for risk evaluation."""
    fixture_id: int
    selection: str
    market_type: str
    market_line: Optional[str]
    odd: float
    stake: float
    kelly_stake: float
    model_prob: float
    edge: float
    ev: float
    confidence: float
    bookmaker_id: int
    bookmaker_name: str
    is_live: bool = False


@dataclass
class RiskAssessment:
    """Risk assessment result."""
    approved: bool
    risk_level: RiskLevel
    adjusted_stake: float
    warnings: List[str]
    rejected_reasons: List[str]
    exposure_impact: Dict[str, float]


@dataclass
class PortfolioState:
    """Current portfolio/bankroll state."""
    bankroll: float
    initial_bankroll: float
    current_exposure: float
    daily_exposure: float
    weekly_exposure: float
    open_bets: List[Dict]
    recent_results: List[Dict]
    max_drawdown: float
    current_drawdown: float
    last_updated: datetime


class RiskManager:
    """Manages betting risk and exposure."""

    def __init__(self, limits: ExposureLimits = None):
        self.limits = limits or ExposureLimits()
        self.portfolio: Optional[PortfolioState] = None

    def initialize_portfolio(
        self,
        bankroll: float,
        initial_bankroll: float = None,
    ):
        """Initialize portfolio state."""
        self.portfolio = PortfolioState(
            bankroll=bankroll,
            initial_bankroll=initial_bankroll or bankroll,
            current_exposure=0.0,
            daily_exposure=0.0,
            weekly_exposure=0.0,
            open_bets=[],
            recent_results=[],
            max_drawdown=0.0,
            current_drawdown=0.0,
            last_updated=datetime.utcnow(),
        )

    def update_portfolio(
        self,
        bankroll: float,
        open_bets: List[Dict] = None,
        recent_results: List[Dict] = None,
    ):
        """Update portfolio state."""
        if not self.portfolio:
            self.initialize_portfolio(bankroll)
            return

        self.portfolio.bankroll = bankroll
        self.portfolio.open_bets = open_bets or []
        self.portfolio.recent_results = recent_results or []
        self.portfolio.last_updated = datetime.utcnow()

        # Recalculate exposures
        self._recalculate_exposures()

        # Update drawdown
        peak = self.portfolio.initial_bankroll
        for result in self.portfolio.recent_results:
            peak = max(peak, result.get("bankroll_after", peak))

        self.portfolio.max_drawdown = max(
            self.portfolio.max_drawdown,
            (peak - bankroll) / peak if peak > 0 else 0
        )
        self.portfolio.current_drawdown = (
            (peak - bankroll) / peak if peak > 0 else 0
        )

    def _recalculate_exposures(self):
        """Recalculate current exposures."""
        if not self.portfolio:
            return

        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(weeks=1)

        current = 0.0
        daily = 0.0
        weekly = 0.0

        for bet in self.portfolio.open_bets:
            stake = bet.get("stake", 0)
            bet_time = bet.get("timestamp")
            if isinstance(bet_time, str):
                bet_time = datetime.fromisoformat(bet_time)

            current += stake
            if bet_time >= day_ago:
                daily += stake
            if bet_time >= week_ago:
                weekly += stake

        self.portfolio.current_exposure = current / self.portfolio.bankroll if self.portfolio.bankroll > 0 else 0
        self.portfolio.daily_exposure = daily / self.portfolio.bankroll if self.portfolio.bankroll > 0 else 0
        self.portfolio.weekly_exposure = weekly / self.portfolio.bankroll if self.portfolio.bankroll > 0 else 0

    def assess_bet(self, proposal: BetProposal) -> RiskAssessment:
        """Assess a proposed bet for risk."""
        if not self.portfolio:
            return RiskAssessment(
                approved=False,
                risk_level=RiskLevel.CRITICAL,
                adjusted_stake=0,
                warnings=["Portfolio not initialized"],
                rejected_reasons=["Portfolio not initialized"],
                exposure_impact={},
            )

        warnings = []
        rejected = []
        adjusted_stake = proposal.stake

        # Check bankroll
        if proposal.stake > self.portfolio.bankroll:
            rejected.append("Stake exceeds bankroll")
            adjusted_stake = 0

        # Check per-match limit
        match_exposure = self._get_match_exposure(proposal.fixture_id)
        new_match_exposure = match_exposure + proposal.stake
        if new_match_exposure / self.portfolio.bankroll > self.limits.max_per_match:
            max_stake = self.portfolio.bankroll * self.limits.max_per_match - match_exposure
            if max_stake < proposal.stake:
                warnings.append(f"Stake reduced to respect per-match limit: {max_stake:.2f}")
                adjusted_stake = min(adjusted_stake, max(0, max_stake))

        # Check per-market limit
        market_exposure = self._get_market_exposure(proposal.market_type)
        new_market_exposure = market_exposure + proposal.stake
        if new_market_exposure / self.portfolio.bankroll > self.limits.max_per_market:
            max_stake = self.portfolio.bankroll * self.limits.max_per_market - market_exposure
            if max_stake < adjusted_stake:
                warnings.append(f"Stake reduced to respect per-market limit: {max_stake:.2f}")
                adjusted_stake = min(adjusted_stake, max(0, max_stake))

        # Check per-bookmaker limit
        bm_exposure = self._get_bookmaker_exposure(proposal.bookmaker_id)
        new_bm_exposure = bm_exposure + proposal.stake
        if new_bm_exposure / self.portfolio.bankroll > self.limits.max_per_bookmaker:
            max_stake = self.portfolio.bankroll * self.limits.max_per_bookmaker - bm_exposure
            if max_stake < adjusted_stake:
                warnings.append(f"Stake reduced to respect per-bookmaker limit: {max_stake:.2f}")
                adjusted_stake = min(adjusted_stake, max(0, max_stake))

        # Check daily limit
        new_daily = self.portfolio.daily_exposure + proposal.stake / self.portfolio.bankroll
        if new_daily > self.limits.max_daily:
            max_stake = (self.limits.max_daily - self.portfolio.daily_exposure) * self.portfolio.bankroll
            if max_stake < adjusted_stake:
                warnings.append(f"Stake reduced to respect daily limit: {max_stake:.2f}")
                adjusted_stake = min(adjusted_stake, max(0, max_stake))

        # Check weekly limit
        new_weekly = self.portfolio.weekly_exposure + proposal.stake / self.portfolio.bankroll
        if new_weekly > self.limits.max_weekly:
            max_stake = (self.limits.max_weekly - self.portfolio.weekly_exposure) * self.portfolio.bankroll
            if max_stake < adjusted_stake:
                warnings.append(f"Stake reduced to respect weekly limit: {max_stake:.2f}")
                adjusted_stake = min(adjusted_stake, max(0, max_stake))

        # Check drawdown limit
        if self.portfolio.current_drawdown > self.limits.max_drawdown:
            rejected.append(f"Max drawdown exceeded: {self.portfolio.current_drawdown:.1%}")

        # Check concurrent bets limit
        if len(self.portfolio.open_bets) >= self.limits.max_concurrent_bets:
            rejected.append(f"Max concurrent bets reached: {self.limits.max_concurrent_bets}")

        # Check Kelly stake vs proposed stake
        if proposal.stake > proposal.kelly_stake * 1.5:
            warnings.append("Stake exceeds 1.5x Kelly recommendation")

        # Check confidence
        if proposal.confidence < 0.5:
            warnings.append("Low model confidence")

        # Check edge
        if proposal.edge < 0.02:
            warnings.append("Low edge")

        # Determine risk level
        total_exposure_pct = (self.portfolio.current_exposure + adjusted_stake / self.portfolio.bankroll) * 100
        if total_exposure_pct > 15:
            risk_level = RiskLevel.HIGH
        elif total_exposure_pct > 10:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        if self.portfolio.current_drawdown > self.limits.max_drawdown * 0.8:
            risk_level = RiskLevel.CRITICAL

        approved = len(rejected) == 0 and adjusted_stake > 0

        exposure_impact = {
            "match_exposure_pct": (match_exposure + adjusted_stake) / self.portfolio.bankroll * 100,
            "market_exposure_pct": (market_exposure + adjusted_stake) / self.portfolio.bankroll * 100,
            "bookmaker_exposure_pct": (bm_exposure + adjusted_stake) / self.portfolio.bankroll * 100,
            "daily_exposure_pct": (self.portfolio.daily_exposure + adjusted_stake / self.portfolio.bankroll) * 100,
            "weekly_exposure_pct": (self.portfolio.weekly_exposure + adjusted_stake / self.portfolio.bankroll) * 100,
            "total_exposure_pct": total_exposure_pct,
            "drawdown_pct": self.portfolio.current_drawdown * 100,
        }

        return RiskAssessment(
            approved=approved,
            risk_level=risk_level,
            adjusted_stake=max(0, adjusted_stake),
            warnings=warnings,
            rejected_reasons=rejected,
            exposure_impact=exposure_impact,
        )

    def _get_match_exposure(self, fixture_id: int) -> float:
        """Get current exposure on a specific match."""
        if not self.portfolio:
            return 0.0
        return sum(
            b.get("stake", 0)
            for b in self.portfolio.open_bets
            if b.get("fixture_id") == fixture_id
        )

    def _get_market_exposure(self, market_type: str) -> float:
        """Get current exposure on a market type."""
        if not self.portfolio:
            return 0.0
        return sum(
            b.get("stake", 0)
            for b in self.portfolio.open_bets
            if b.get("market_type") == market_type
        )

    def _get_bookmaker_exposure(self, bookmaker_id: int) -> float:
        """Get current exposure with a bookmaker."""
        if not self.portfolio:
            return 0.0
        return sum(
            b.get("stake", 0)
            for b in self.portfolio.open_bets
            if b.get("bookmaker_id") == bookmaker_id
        )

    def assess_portfolio(self) -> Dict:
        """Assess overall portfolio risk."""
        if not self.portfolio:
            return {"error": "Portfolio not initialized"}

        return {
            "bankroll": self.portfolio.bankroll,
            "initial_bankroll": self.portfolio.initial_bankroll,
            "profit_loss": self.portfolio.bankroll - self.portfolio.initial_bankroll,
            "roi_percent": (self.portfolio.bankroll - self.portfolio.initial_bankroll) / self.portfolio.initial_bankroll * 100,
            "current_exposure_pct": self.portfolio.current_exposure * 100,
            "daily_exposure_pct": self.portfolio.daily_exposure * 100,
            "weekly_exposure_pct": self.portfolio.weekly_exposure * 100,
            "max_drawdown_pct": self.portfolio.max_drawdown * 100,
            "current_drawdown_pct": self.portfolio.current_drawdown * 100,
            "open_bets_count": len(self.portfolio.open_bets),
            "risk_level": self._get_overall_risk_level().value,
            "limits": {
                "max_per_match": self.limits.max_per_match,
                "max_per_market": self.limits.max_per_market,
                "max_per_bookmaker": self.limits.max_per_bookmaker,
                "max_daily": self.limits.max_daily,
                "max_weekly": self.limits.max_weekly,
                "max_drawdown": self.limits.max_drawdown,
                "max_concurrent_bets": self.limits.max_concurrent_bets,
            },
        }

    def _get_overall_risk_level(self) -> RiskLevel:
        """Get overall portfolio risk level."""
        if self.portfolio.current_drawdown > self.limits.max_drawdown:
            return RiskLevel.CRITICAL
        elif self.portfolio.current_drawdown > self.limits.max_drawdown * 0.7:
            return RiskLevel.HIGH
        elif self.portfolio.current_exposure > 0.15:
            return RiskLevel.HIGH
        elif self.portfolio.current_exposure > 0.10:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def get_recommended_stake(
        self,
        kelly_stake: float,
        confidence: float,
        edge: float,
    ) -> float:
        """Get recommended stake adjusted for risk."""
        # Base stake from Kelly
        stake = kelly_stake

        # Adjust for confidence
        stake *= confidence

        # Adjust for edge (smaller edge = smaller stake)
        if edge < 0.05:
            stake *= edge / 0.05

        # Cap at max per-match limit
        if self.portfolio:
            max_stake = self.portfolio.bankroll * self.limits.max_per_match
            stake = min(stake, max_stake)

        return max(0, stake)


class BankrollSimulator:
    """Simulate bankroll growth under different strategies."""

    def __init__(self, initial_bankroll: float = 1000.0):
        self.initial_bankroll = initial_bankroll
        self.history: List[Dict] = []

    def simulate(
        self,
        bets: List[Dict],
        strategy: str = "fractional_kelly",
        kelly_fraction: float = 0.25,
    ) -> Dict:
        """Run bankroll simulation."""
        bankroll = self.initial_bankroll
        peak = bankroll
        max_drawdown = 0.0
        total_staked = 0.0
        total_returned = 0.0
        wins = 0
        losses = 0
        pushes = 0

        self.history = [{
            "step": 0,
            "bankroll": bankroll,
            "bet": None,
            "stake": 0,
            "result": None,
            "profit": 0,
            "drawdown": 0,
        }]

        for i, bet in enumerate(bets):
            model_prob = bet.get("model_prob", 0.5)
            odd = bet.get("odd", 2.0)
            edge = bet.get("edge", 0)
            ev = bet.get("ev", 0)

            # Determine stake based on strategy
            if strategy == "flat":
                stake = bankroll * 0.01  # 1% flat
            elif strategy == "kelly":
                b = odd - 1
                p = model_prob
                q = 1 - p
                kelly = (b * p - q) / b if b > 0 else 0
                stake = bankroll * max(0, kelly)
            elif strategy == "fractional_kelly":
                b = odd - 1
                p = model_prob
                q = 1 - p
                kelly = (b * p - q) / b if b > 0 else 0
                stake = bankroll * max(0, kelly * kelly_fraction)
            elif strategy == "proportional_edge":
                stake = bankroll * min(0.05, edge * 2)
            else:
                stake = bankroll * 0.01

            stake = min(stake, bankroll * 0.05)  # Cap at 5%

            # Simulate result
            import random
            won = random.random() < model_prob

            if won:
                profit = stake * (odd - 1)
                bankroll += profit
                total_returned += stake * odd
                wins += 1
                result = "win"
            else:
                profit = -stake
                bankroll -= stake
                losses += 1
                result = "loss"

            total_staked += stake

            # Track drawdown
            peak = max(peak, bankroll)
            drawdown = (peak - bankroll) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

            self.history.append({
                "step": i + 1,
                "bankroll": bankroll,
                "bet": bet,
                "stake": stake,
                "result": result,
                "profit": profit,
                "drawdown": drawdown * 100,
            })

        roi = (bankroll - self.initial_bankroll) / self.initial_bankroll * 100
        yield_pct = (total_returned - total_staked) / total_staked * 100 if total_staked > 0 else 0

        return {
            "final_bankroll": bankroll,
            "initial_bankroll": self.initial_bankroll,
            "profit": bankroll - self.initial_bankroll,
            "roi_percent": roi,
            "yield_percent": yield_pct,
            "total_staked": total_staked,
            "total_returned": total_returned,
            "total_bets": len(bets),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": wins / len(bets) * 100 if bets else 0,
            "max_drawdown_percent": max_drawdown * 100,
            "avg_stake": total_staked / len(bets) if bets else 0,
            "history": self.history,
        }

    def run_monte_carlo(
        self,
        bets: List[Dict],
        simulations: int = 1000,
        strategy: str = "fractional_kelly",
        kelly_fraction: float = 0.25,
    ) -> Dict:
        """Run Monte Carlo simulation."""
        results = []

        for _ in range(simulations):
            sim_result = self.simulate(bets, strategy, kelly_fraction)
            results.append({
                "final_bankroll": sim_result["final_bankroll"],
                "roi": sim_result["roi_percent"],
                "max_drawdown": sim_result["max_drawdown_percent"],
                "profit": sim_result["profit"],
            })

        # Percentiles
        final_bankrolls = sorted([r["final_bankroll"] for r in results])
        rois = sorted([r["roi"] for r in results])
        drawdowns = sorted([r["max_drawdown"] for r in results])

        def percentile(arr, p):
            idx = int(len(arr) * p / 100)
            return arr[min(idx, len(arr) - 1)]

        return {
            "simulations": simulations,
            "mean_final_bankroll": sum(final_bankrolls) / len(final_bankrolls),
            "median_final_bankroll": final_bankrolls[len(final_bankrolls) // 2],
            "p5_final_bankroll": percentile(final_bankrolls, 5),
            "p95_final_bankroll": percentile(final_bankrolls, 95),
            "mean_roi": sum(rois) / len(rois),
            "median_roi": rois[len(rois) // 2],
            "p5_roi": percentile(rois, 5),
            "p95_roi": percentile(rois, 95),
            "mean_max_drawdown": sum(drawdowns) / len(drawdowns),
            "median_max_drawdown": drawdowns[len(drawdowns) // 2],
            "p95_max_drawdown": percentile(drawdowns, 95),
            "prob_profit": sum(1 for r in results if r["profit"] > 0) / simulations * 100,
            "prob_ruin": sum(1 for r in results if r["final_bankroll"] < self.initial_bankroll * 0.5) / simulations * 100,
        }