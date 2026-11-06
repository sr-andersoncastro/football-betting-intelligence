"""Database models for Football Betting Intelligence."""
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Time, Float, Boolean,
    Text, ForeignKey, Index, UniqueConstraint, Enum, DECIMAL, JSON
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Competition(Base):
    """Football competitions/leagues."""
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True, autoincrement=False)  # External API ID
    name = Column(String(200), nullable=False)
    country = Column(String(100), nullable=True)
    logo_url = Column(String(500), nullable=True)
    type = Column(String(50), nullable=True)  # league, cup, etc.
    current_season = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    seasons = relationship("Season", back_populates="competition")
    teams = relationship("Team", back_populates="competition")


class Season(Base):
    """Competition seasons."""
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    year = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    competition = relationship("Competition", back_populates="seasons")
    fixtures = relationship("Fixture", back_populates="season")

    __table_args__ = (
        UniqueConstraint("competition_id", "year", name="uq_competition_year"),
    )


class Team(Base):
    """Football teams."""
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=False)  # External API ID
    name = Column(String(200), nullable=False)
    short_name = Column(String(50), nullable=True)
    country = Column(String(100), nullable=True)
    logo_url = Column(String(500), nullable=True)
    venue_name = Column(String(200), nullable=True)
    venue_city = Column(String(100), nullable=True)
    venue_capacity = Column(Integer, nullable=True)
    founded = Column(Integer, nullable=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=True)
    is_national = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    competition = relationship("Competition", back_populates="teams")
    home_fixtures = relationship("Fixture", foreign_keys="Fixture.home_team_id", back_populates="home_team")
    away_fixtures = relationship("Fixture", foreign_keys="Fixture.away_team_id", back_populates="away_team")
    statistics = relationship("TeamStatistics", back_populates="team")


class Fixture(Base):
    """Football matches/fixtures."""
    __tablename__ = "fixtures"

    id = Column(Integer, primary_key=True, autoincrement=False)  # External API ID
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    timestamp = Column(Integer, nullable=True)
    timezone = Column(String(50), nullable=True)
    venue_id = Column(Integer, nullable=True)
    referee_id = Column(Integer, ForeignKey("referees.id"), nullable=True)
    status_short = Column(String(10), nullable=True)  # NS, 1H, HT, 2H, FT, etc.
    status_long = Column(String(50), nullable=True)
    status_elapsed = Column(Integer, nullable=True)
    round = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    season = relationship("Season", back_populates="fixtures")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_fixtures")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_fixtures")
    referee = relationship("Referee", back_populates="fixtures")
    events = relationship("FixtureEvent", back_populates="fixture")
    statistics = relationship("FixtureStatistics", back_populates="fixture")
    lineups = relationship("FixtureLineup", back_populates="fixture")
    odds = relationship("FixtureOdds", back_populates="fixture")
    predictions = relationship("ModelPrediction", back_populates="fixture")


class FixtureEvent(Base):
    """Events within a fixture (goals, cards, substitutions, etc.)."""
    __tablename__ = "fixture_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    time_elapsed = Column(Integer, nullable=True)
    time_extra = Column(Integer, nullable=True)
    type = Column(String(20), nullable=False)  # Goal, Card, Subst, Var
    detail = Column(String(100), nullable=True)  # Normal Goal, Yellow Card, etc.
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    fixture = relationship("Fixture", back_populates="events")
    team = relationship("Team")
    player = relationship("Player")


class FixtureStatistics(Base):
    """Team statistics for a fixture."""
    __tablename__ = "fixture_statistics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    type = Column(String(50), nullable=False)  # Shots on Goal, Total Shots, etc.
    value = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now())

    fixture = relationship("Fixture", back_populates="statistics")
    team = relationship("Team")

    __table_args__ = (
        Index("ix_fixture_stats_fixture_team_type", "fixture_id", "team_id", "type"),
    )


class FixtureLineup(Base):
    """Team lineups for a fixture."""
    __tablename__ = "fixture_lineups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    formation = Column(String(20), nullable=True)
    is_starting = Column(Boolean, default=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    number = Column(Integer, nullable=True)
    position = Column(String(20), nullable=True)
    grid = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=func.now())

    fixture = relationship("Fixture", back_populates="lineups")
    team = relationship("Team")
    player = relationship("Player")


class Player(Base):
    """Football players."""
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, autoincrement=False)  # External API ID
    name = Column(String(200), nullable=False)
    firstname = Column(String(100), nullable=True)
    lastname = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    birth_date = Column(Date, nullable=True)
    birth_place = Column(String(200), nullable=True)
    birth_country = Column(String(100), nullable=True)
    nationality = Column(String(100), nullable=True)
    height = Column(String(20), nullable=True)
    weight = Column(String(20), nullable=True)
    photo_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    events = relationship("FixtureEvent", back_populates="player")
    lineups = relationship("FixtureLineup", back_populates="player")
    statistics = relationship("PlayerStatistics", back_populates="player")


class PlayerStatistics(Base):
    """Player statistics per season."""
    __tablename__ = "player_statistics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    appearances = Column(Integer, default=0)
    minutes_played = Column(Integer, default=0)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    shots_total = Column(Integer, default=0)
    shots_on_target = Column(Integer, default=0)
    passes_total = Column(Integer, default=0)
    passes_accuracy = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    player = relationship("Player", back_populates="statistics")
    team = relationship("Team")
    season = relationship("Season")
    competition = relationship("Competition")


class Referee(Base):
    """Match referees."""
    __tablename__ = "referees"

    id = Column(Integer, primary_key=True, autoincrement=False)  # External API ID
    name = Column(String(200), nullable=False)
    country = Column(String(100), nullable=True)
    photo_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=func.now())

    fixtures = relationship("Fixture", back_populates="referee")
    statistics = relationship("RefereeStatistics", back_populates="referee")


class RefereeStatistics(Base):
    """Referee statistics per season."""
    __tablename__ = "referee_statistics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referee_id = Column(Integer, ForeignKey("referees.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    matches = Column(Integer, default=0)
    yellow_cards_per_game = Column(Float, nullable=True)
    red_cards_per_game = Column(Float, nullable=True)
    penalties_per_game = Column(Float, nullable=True)
    home_wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    away_wins = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    referee = relationship("Referee", back_populates="statistics")
    season = relationship("Season")
    competition = relationship("Competition")


class TeamStatistics(Base):
    """Team statistics per season."""
    __tablename__ = "team_statistics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    season_id = Column(Integer, ForeignKey("seasons.id"), nullable=False)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    form = Column(String(50), nullable=True)
    played = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    goals_for_home = Column(Integer, default=0)
    goals_against_home = Column(Integer, default=0)
    goals_for_away = Column(Integer, default=0)
    goals_against_away = Column(Integer, default=0)
    clean_sheets = Column(Integer, default=0)
    clean_sheets_home = Column(Integer, default=0)
    clean_sheets_away = Column(Integer, default=0)
    failed_to_score = Column(Integer, default=0)
    failed_to_score_home = Column(Integer, default=0)
    failed_to_score_away = Column(Integer, default=0)
    penalties_scored = Column(Integer, default=0)
    penalties_missed = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    team = relationship("Team", back_populates="statistics")
    season = relationship("Season")
    competition = relationship("Competition")

    __table_args__ = (
        UniqueConstraint("team_id", "season_id", name="uq_team_season"),
    )


class Bookmaker(Base):
    """Bookmakers/betting houses."""
    __tablename__ = "bookmakers"

    id = Column(Integer, primary_key=True, autoincrement=False)  # External API ID
    name = Column(String(200), nullable=False)
    logo_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    odds = relationship("FixtureOdds", back_populates="bookmaker")


class MarketType(PyEnum):
    """Types of betting markets."""
    MATCH_WINNER = "match_winner"  # 1X2
    OVER_UNDER = "over_under"
    BOTH_TEAMS_SCORE = "both_teams_score"
    ASIAN_HANDICAP = "asian_handicap"
    CORNERS = "corners"
    CARDS = "cards"
    CORRECT_SCORE = "correct_score"
    HALF_TIME_FULL_TIME = "half_time_full_time"
    DOUBLE_CHANCE = "double_chance"
    DRAW_NO_BET = "draw_no_bet"


class FixtureOdds(Base):
    """Odds for fixtures from bookmakers."""
    __tablename__ = "fixture_odds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=False)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)
    market_type = Column(Enum(MarketType), nullable=False)
    market_name = Column(String(100), nullable=True)  # e.g., "Over 2.5", "Asian Handicap -0.25"
    value = Column(String(50), nullable=True)  # Line value for handicap/over-under
    odd_home = Column(Float, nullable=True)  # 1 / Over / Yes
    odd_draw = Column(Float, nullable=True)  # X / N/A / N/A
    odd_away = Column(Float, nullable=True)  # 2 / Under / No
    odd_handicap = Column(Float, nullable=True)  # For Asian handicap lines
    is_live = Column(Boolean, default=False)
    last_update = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    fixture = relationship("Fixture", back_populates="odds")
    bookmaker = relationship("Bookmaker", back_populates="odds")

    __table_args__ = (
        Index("ix_fixture_odds_fixture_market", "fixture_id", "market_type", "bookmaker_id"),
        Index("ix_fixture_odds_live", "is_live", "last_update"),
    )


class ModelVersion(Base):
    """Model versions for tracking."""
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # poisson_dixon_coles, elo, corners_poisson, etc.
    version = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    parameters = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    predictions = relationship("ModelPrediction", back_populates="model_version")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_model_version"),
    )


class ModelPrediction(Base):
    """Model predictions for fixtures."""
    __tablename__ = "model_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=False)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=False)
    market_type = Column(Enum(MarketType), nullable=False)
    market_line = Column(String(50), nullable=True)  # e.g., "2.5" for Over/Under

    # Probabilities
    prob_home = Column(Float, nullable=True)
    prob_draw = Column(Float, nullable=True)
    prob_away = Column(Float, nullable=True)
    prob_over = Column(Float, nullable=True)
    prob_under = Column(Float, nullable=True)
    prob_bts_yes = Column(Float, nullable=True)
    prob_bts_no = Column(Float, nullable=True)

    # Value betting metrics
    edge_home = Column(Float, nullable=True)
    edge_draw = Column(Float, nullable=True)
    edge_away = Column(Float, nullable=True)
    edge_over = Column(Float, nullable=True)
    edge_under = Column(Float, nullable=True)
    edge_bts_yes = Column(Float, nullable=True)
    edge_bts_no = Column(Float, nullable=True)

    ev_home = Column(Float, nullable=True)
    ev_draw = Column(Float, nullable=True)
    ev_away = Column(Float, nullable=True)
    ev_over = Column(Float, nullable=True)
    ev_under = Column(Float, nullable=True)
    ev_bts_yes = Column(Float, nullable=True)
    ev_bts_no = Column(Float, nullable=True)

    confidence = Column(Float, nullable=True)
    data_quality_score = Column(Float, nullable=True)
    prediction_time = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())

    fixture = relationship("Fixture", back_populates="predictions")
    model_version = relationship("ModelVersion", back_populates="predictions")

    __table_args__ = (
        Index("ix_predictions_fixture_model_market", "fixture_id", "model_version_id", "market_type"),
        Index("ix_predictions_edge", "edge_home", "edge_draw", "edge_away"),
    )


class PredictionResult(Base):
    """Actual results for predictions."""
    __tablename__ = "prediction_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(Integer, ForeignKey("model_predictions.id"), nullable=False)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=False)

    # Actual result
    result_home = Column(Integer, nullable=True)
    result_draw = Column(Integer, nullable=True)
    result_away = Column(Integer, nullable=True)
    result_over = Column(Integer, nullable=True)
    result_under = Column(Integer, nullable=True)
    result_bts_yes = Column(Integer, nullable=True)
    result_bts_no = Column(Integer, nullable=True)
    result_corners_over = Column(Integer, nullable=True)
    result_cards_over = Column(Integer, nullable=True)

    # Outcome
    is_correct_home = Column(Boolean, nullable=True)
    is_correct_draw = Column(Boolean, nullable=True)
    is_correct_away = Column(Boolean, nullable=True)
    is_correct_over = Column(Boolean, nullable=True)
    is_correct_under = Column(Boolean, nullable=True)
    is_correct_bts = Column(Boolean, nullable=True)

    # Accuracy metrics
    brier_score = Column(Float, nullable=True)
    log_loss = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())

    prediction = relationship("ModelPrediction")
    fixture = relationship("Fixture")


class BacktestRun(Base):
    """Backtesting runs."""
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    competitions = Column(JSON, nullable=True)  # List of competition IDs
    markets = Column(JSON, nullable=True)  # List of market types
    min_edge = Column(Float, nullable=True)
    min_confidence = Column(Float, nullable=True)
    stake_strategy = Column(String(50), nullable=True)  # flat, kelly, fractional_kelly
    kelly_fraction = Column(Float, nullable=True)
    total_bets = Column(Integer, default=0)
    winning_bets = Column(Integer, default=0)
    total_stake = Column(Float, default=0.0)
    total_return = Column(Float, default=0.0)
    roi = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    yield_percent = Column(Float, nullable=True)
    clv = Column(Float, nullable=True)  # Closing Line Value
    brier_score = Column(Float, nullable=True)
    log_loss = Column(Float, nullable=True)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)

    model_version = relationship("ModelVersion")
    bets = relationship("BacktestBet", back_populates="backtest_run")


class BacktestBet(Base):
    """Individual bets in a backtest."""
    __tablename__ = "backtest_bets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    backtest_run_id = Column(Integer, ForeignKey("backtest_runs.id"), nullable=False)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=False)
    prediction_id = Column(Integer, ForeignKey("model_predictions.id"), nullable=True)
    market_type = Column(Enum(MarketType), nullable=False)
    market_line = Column(String(50), nullable=True)
    selection = Column(String(20), nullable=False)  # home, draw, away, over, under, bts_yes, bts_no
    odd = Column(Float, nullable=False)
    prob_model = Column(Float, nullable=False)
    prob_implied = Column(Float, nullable=False)
    edge = Column(Float, nullable=False)
    ev = Column(Float, nullable=False)
    stake = Column(Float, nullable=False)
    result = Column(String(20), nullable=True)  # win, loss, push, void
    profit = Column(Float, nullable=True)
    bankroll_before = Column(Float, nullable=True)
    bankroll_after = Column(Float, nullable=True)
    bet_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())

    backtest_run = relationship("BacktestRun", back_populates="bets")
    fixture = relationship("Fixture")
    prediction = relationship("ModelPrediction")


class SyncLog(Base):
    """Synchronization logs."""
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False)  # api_football, football_data, odds_api
    operation = Column(String(50), nullable=False)  # competitions, fixtures, odds, statistics
    competition_id = Column(Integer, nullable=True)
    season = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False)  # success, partial, failed
    records_processed = Column(Integer, default=0)
    records_created = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_sync_logs_provider_operation", "provider", "operation", "started_at"),
    )


class BankrollSimulation(Base):
    """Bankroll simulation configurations and results."""
    __tablename__ = "bankroll_simulations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    initial_bankroll = Column(Float, nullable=False)
    current_bankroll = Column(Float, nullable=False)
    peak_bankroll = Column(Float, nullable=False)
    max_drawdown = Column(Float, default=0.0)
    max_drawdown_percent = Column(Float, default=0.0)
    total_bets = Column(Integer, default=0)
    winning_bets = Column(Integer, default=0)
    roi = Column(Float, nullable=True)
    kelly_fraction = Column(Float, nullable=True)
    min_edge = Column(Float, nullable=True)
    min_confidence = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    bets = relationship("BankrollBet", back_populates="simulation")


class BankrollBet(Base):
    """Individual bets in bankroll simulation."""
    __tablename__ = "bankroll_bets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_id = Column(Integer, ForeignKey("bankroll_simulations.id"), nullable=False)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"), nullable=True)
    market_type = Column(Enum(MarketType), nullable=False)
    market_line = Column(String(50), nullable=True)
    selection = Column(String(20), nullable=False)
    odd = Column(Float, nullable=False)
    stake = Column(Float, nullable=False)
    unit_size = Column(Float, nullable=True)
    result = Column(String(20), nullable=True)
    profit = Column(Float, nullable=True)
    bankroll_before = Column(Float, nullable=False)
    bankroll_after = Column(Float, nullable=False)
    bet_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())

    simulation = relationship("BankrollSimulation", back_populates="bets")
    fixture = relationship("Fixture")