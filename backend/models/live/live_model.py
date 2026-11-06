"""Live/in-play match models."""
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum


class MatchState(Enum):
    """Current state of the match."""
    PRE_MATCH = "pre_match"
    FIRST_HALF = "first_half"
    HALF_TIME = "half_time"
    SECOND_HALF = "second_half"
    EXTRA_TIME = "extra_time"
    PENALTIES = "penalties"
    FINISHED = "finished"
    SUSPENDED = "suspended"
    POSTPONED = "postponed"


@dataclass
class LiveMatchState:
    """Current live match state."""
    fixture_id: int
    minute: int
    added_time: int
    state: MatchState
    home_score: int
    away_score: int
    home_shots: int = 0
    away_shots: int = 0
    home_shots_on_target: int = 0
    away_shots_on_target: int = 0
    home_corners: int = 0
    away_corners: int = 0
    home_yellow_cards: int = 0
    away_yellow_cards: int = 0
    home_red_cards: int = 0
    away_red_cards: int = 0
    home_possession: float = 50.0
    away_possession: float = 50.0
    home_xg: float = 0.0
    away_xg: float = 0.0
    pressure_index: float = 0.0  # 0-100
    last_event_time: Optional[datetime] = None
    last_event_type: Optional[str] = None


@dataclass
class LivePrediction:
    """Live prediction output."""
    match_state: LiveMatchState
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    total_goals_expected: float
    next_goal_probability: Dict[str, float]  # home, away, none
    over_under_live: Dict[float, Tuple[float, float]]
    time_to_next_goal: Optional[float]
    win_probability_trend: List[Tuple[int, float, float, float]]  # (minute, home, draw, away)


class LiveModel:
    """Model for live/in-play predictions."""

    def __init__(self):
        self.pre_match_home_win: float = 0.0
        self.pre_match_draw: float = 0.0
        self.pre_match_away_win: float = 0.0
        self.pre_match_xg_home: float = 0.0
        self.pre_match_xg_away: float = 0.0

        # Decay parameters
        self.goal_decay_rate: float = 0.02  # Per minute
        self.xg_decay_rate: float = 0.01

    def initialize_from_pre_match(
        self,
        home_win: float,
        draw: float,
        away_win: float,
        xg_home: float,
        xg_away: float,
    ):
        """Initialize from pre-match predictions."""
        self.pre_match_home_win = home_win
        self.pre_match_draw = draw
        self.pre_match_away_win = away_win
        self.pre_match_xg_home = xg_home
        self.pre_match_xg_away = xg_away

    def update(self, match_state: LiveMatchState) -> LivePrediction:
        """Update predictions based on live state."""
        # Calculate time remaining
        if match_state.state == MatchState.FIRST_HALF:
            time_elapsed = match_state.minute
            time_remaining = 45 - match_state.minute + match_state.added_time
        elif match_state.state == MatchState.HALF_TIME:
            time_elapsed = 45
            time_remaining = 45
        elif match_state.state == MatchState.SECOND_HALF:
            time_elapsed = 45 + match_state.minute
            time_remaining = 90 - match_state.minute + match_state.added_time
        else:
            time_elapsed = 90
            time_remaining = 0

        total_time = 90
        time_fraction = max(0, time_remaining / total_time)

        # Adjust expected goals based on current score and xG
        goals_scored_home = match_state.home_score
        goals_scored_away = match_state.away_score

        # xG accumulated so far
        xg_so_far_home = match_state.home_xg
        xg_so_far_away = match_state.away_xg

        # Expected remaining xG
        remaining_xg_home = max(0, self.pre_match_xg_home - xg_so_far_home) * time_fraction
        remaining_xg_away = max(0, self.pre_match_xg_away - xg_so_far_away) * time_fraction

        # Total expected final xG
        total_xg_home = xg_so_far_home + remaining_xg_home
        total_xg_away = xg_so_far_away + remaining_xg_away

        # Score difference
        score_diff = goals_scored_home - goals_scored_away

        # Calculate win probabilities using adjusted Dixon-Coles
        home_win, draw, away_win = self._calculate_live_probabilities(
            goals_scored_home, goals_scored_away,
            remaining_xg_home, remaining_xg_away,
            time_fraction
        )

        # Next goal probability
        next_goal = self._calculate_next_goal_probability(
            remaining_xg_home, remaining_xg_away, time_remaining
        )

        # Over/Under live
        over_under = self._calculate_live_over_under(
            goals_scored_home + goals_scored_away,
            remaining_xg_home + remaining_xg_away,
        )

        # Time to next goal
        total_remaining_xg = remaining_xg_home + remaining_xg_away
        if total_remaining_xg > 0:
            time_to_next = 90 / total_remaining_xg * time_fraction
        else:
            time_to_next = None

        return LivePrediction(
            match_state=match_state,
            home_win_prob=home_win,
            draw_prob=draw,
            away_win_prob=away_win,
            total_goals_expected=goals_scored_home + goals_scored_away + total_remaining_xg,
            next_goal_probability=next_goal,
            over_under_live=over_under,
            time_to_next_goal=time_to_next,
            win_probability_trend=[],  # Would track historical
        )

    def _calculate_live_probabilities(
        self,
        home_goals: int,
        away_goals: int,
        rem_xg_home: float,
        rem_xg_away: float,
        time_frac: float,
    ) -> Tuple[float, float, float]:
        """Calculate live win/draw/loss probabilities."""
        from scipy.stats import poisson

        max_goals = 8
        score_probs = {}

        # Current score as base
        for add_h in range(max_goals + 1):
            for add_a in range(max_goals + 1):
                prob = poisson.pmf(add_h, rem_xg_home) * poisson.pmf(add_a, rem_xg_away)
                final_h = home_goals + add_h
                final_a = away_goals + add_a
                score_probs[(final_h, final_a)] = prob

        home_win = sum(p for (h, a), p in score_probs.items() if h > a)
        draw = sum(p for (h, a), p in score_probs.items() if h == a)
        away_win = sum(p for (h, a), p in score_probs.items() if h < a)

        total = home_win + draw + away_win
        if total > 0:
            home_win /= total
            draw /= total
            away_win /= total

        return home_win, draw, away_win

    def _calculate_next_goal_probability(
        self,
        rem_xg_home: float,
        rem_xg_away: float,
        time_remaining: int,
    ) -> Dict[str, float]:
        """Calculate probability of next goal."""
        if time_remaining <= 0:
            return {"home": 0.0, "away": 0.0, "none": 1.0}

        total_xg = rem_xg_home + rem_xg_away
        if total_xg == 0:
            return {"home": 0.0, "away": 0.0, "none": 1.0}

        # Probability of at least one goal in remaining time
        prob_any_goal = 1 - math.exp(-total_xg * time_remaining / 90)

        if prob_any_goal == 0:
            return {"home": 0.0, "away": 0.0, "none": 1.0}

        prob_home_next = prob_any_goal * (rem_xg_home / total_xg)
        prob_away_next = prob_any_goal * (rem_xg_away / total_xg)
        prob_none = 1 - prob_any_goal

        return {
            "home": prob_home_next,
            "away": prob_away_next,
            "none": prob_none,
        }

    def _calculate_live_over_under(
        self,
        current_goals: int,
        remaining_xg: float,
    ) -> Dict[float, Tuple[float, float]]:
        """Calculate live over/under probabilities."""
        from scipy.stats import poisson

        over_under = {}
        for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            target = line - current_goals
            if target <= 0:
                over_under[line] = (1.0, 0.0)
            else:
                over = 1 - poisson.cdf(int(target), remaining_xg)
                under = poisson.cdf(int(target), remaining_xg)
                over_under[line] = (over, under)

        return over_under


class LiveModelAdvanced(LiveModel):
    """Advanced live model with momentum and pressure."""

    def __init__(self):
        super().__init__()
        self.momentum_window: int = 5  # minutes
        self.pressure_threshold: float = 70.0

    def update(self, match_state: LiveMatchState) -> LivePrediction:
        """Update with momentum and pressure adjustments."""
        base_pred = super().update(match_state)

        # Calculate momentum
        momentum_factor = self._calculate_momentum(match_state)

        # Adjust probabilities based on momentum
        if momentum_factor > 0:  # Home momentum
            base_pred.home_win_prob *= (1 + momentum_factor * 0.1)
            base_pred.away_win_prob *= (1 - momentum_factor * 0.05)
        elif momentum_factor < 0:  # Away momentum
            base_pred.away_win_prob *= (1 + abs(momentum_factor) * 0.1)
            base_pred.home_win_prob *= (1 - abs(momentum_factor) * 0.05)

        # Normalize
        total = base_pred.home_win_prob + base_pred.draw_prob + base_pred.away_win_prob
        if total > 0:
            base_pred.home_win_prob /= total
            base_pred.draw_prob /= total
            base_pred.away_win_prob /= total

        # Pressure adjustments
        if match_state.pressure_index > self.pressure_threshold:
            # High pressure increases goal expectation
            pressure_boost = (match_state.pressure_index - self.pressure_threshold) / 100 * 0.2
            base_pred.total_goals_expected *= (1 + pressure_boost)

        return base_pred

    def _calculate_momentum(self, match_state: LiveMatchState) -> float:
        """Calculate momentum from recent events."""
        # Simplified: based on shots, corners, possession in last 5-10 minutes
        # In reality, would track event timeline
        shot_ratio = 0
        if match_state.home_shots + match_state.away_shots > 0:
            shot_ratio = (match_state.home_shots - match_state.away_shots) / (match_state.home_shots + match_state.away_shots)

        possession_diff = match_state.home_possession - match_state.away_possession

        # Combine factors
        momentum = shot_ratio * 0.6 + (possession_diff / 100) * 0.4

        # Red card impact
        if match_state.home_red_cards > match_state.away_red_cards:
            momentum -= 0.3
        elif match_state.away_red_cards > match_state.home_red_cards:
            momentum += 0.3

        return max(-1, min(1, momentum))


def create_live_state_from_events(
    fixture_id: int,
    events: List[Dict],
    statistics: List[Dict],
    current_minute: int,
    added_time: int = 0,
) -> LiveMatchState:
    """Create LiveMatchState from fixture events and statistics."""
    home_score = 0
    away_score = 0
    home_shots = away_shots = 0
    home_sot = away_sot = 0
    home_corners = away_corners = 0
    home_yellow = away_yellow = 0
    home_red = away_red = 0
    home_xg = away_xg = 0.0
    last_event_time = None
    last_event_type = None

    # Process events
    for event in events:
        is_home = event.get("team_id") == event.get("home_team_id")  # Would need team mapping
        event_type = event.get("type")
        detail = event.get("detail")
        time_elapsed = event.get("time_elapsed", 0)

        if event_type == "Goal":
            if is_home:
                home_score += 1
            else:
                away_score += 1
        elif event_type == "Card":
            if "Yellow" in str(detail):
                if is_home:
                    home_yellow += 1
                else:
                    away_yellow += 1
            elif "Red" in str(detail):
                if is_home:
                    home_red += 1
                else:
                    away_red += 1

        last_event_time = time_elapsed
        last_event_type = event_type

    # Process statistics
    for stat in statistics:
        team_id = stat.get("team_id")
        stat_type = stat.get("type")
        value = stat.get("value")

        try:
            val = int(value) if value else 0
        except:
            val = 0

        is_home = True  # Would need proper mapping

        if stat_type == "Total Shots":
            if is_home:
                home_shots = val
            else:
                away_shots = val
        elif stat_type == "Shots on Goal":
            if is_home:
                home_sot = val
            else:
                away_sot = val
        elif stat_type == "Corner Kicks":
            if is_home:
                home_corners = val
            else:
                away_corners = val
        elif stat_type == "Expected Goals":
            try:
                xg_val = float(value) if value else 0.0
            except:
                xg_val = 0.0
            if is_home:
                home_xg = xg_val
            else:
                away_xg = xg_val

    # Determine match state
    if current_minute == 0:
        state = MatchState.PRE_MATCH
    elif current_minute <= 45:
        state = MatchState.FIRST_HALF
    elif current_minute == 45:
        state = MatchState.HALF_TIME
    elif current_minute <= 90:
        state = MatchState.SECOND_HALF
    elif current_minute <= 120:
        state = MatchState.EXTRA_TIME
    else:
        state = MatchState.FINISHED

    # Calculate pressure index (simplified)
    total_shots = home_shots + away_shots
    recent_shots_ratio = 0
    if total_shots > 0:
        recent_shots_ratio = home_shots / total_shots

    possession = 50.0  # Would come from stats
    pressure = recent_shots_ratio * 50 + (possession - 50) * 0.5 + 50

    return LiveMatchState(
        fixture_id=fixture_id,
        minute=current_minute,
        added_time=added_time,
        state=state,
        home_score=home_score,
        away_score=away_score,
        home_shots=home_shots,
        away_shots=away_shots,
        home_shots_on_target=home_sot,
        away_shots_on_target=away_sot,
        home_corners=home_corners,
        away_corners=away_corners,
        home_yellow_cards=home_yellow,
        away_yellow_cards=away_yellow,
        home_red_cards=home_red,
        away_red_cards=away_red,
        home_possession=possession,
        away_possession=100 - possession,
        home_xg=home_xg,
        away_xg=away_xg,
        pressure_index=max(0, min(100, pressure)),
        last_event_time=last_event_time,
        last_event_type=last_event_type,
    )