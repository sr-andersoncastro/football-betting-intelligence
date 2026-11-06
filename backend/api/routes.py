"""API routes for Football Betting Intelligence."""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.database.models import (
    Competition, Season, Team, Fixture, FixtureEvent, FixtureStatistics,
    FixtureLineup, Bookmaker, MarketType, FixtureOdds, ModelVersion,
    ModelPrediction, PredictionResult, SyncLog
)
from backend.ingestion.sync_service import SyncService
from backend.models.goals.poisson_model import CombinedGoalsModel, MatchPrediction
from backend.models.corners.corners_model import CornersModel, CornerPrediction
from backend.models.cards.cards_model import CardsModel, CardsPrediction
from backend.models.live.live_model import LiveModel, LiveMatchState, MatchState, create_live_state_from_events
from backend.value_betting.engine import ValueBettingEngine, OddsData, ModelProbabilities, BetSelection
from config.settings import settings

router = APIRouter(prefix=settings.API_V1_PREFIX)


# Health Check
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
    }


# Providers
@router.get("/providers")
async def get_providers():
    """Get available data providers."""
    return {
        "providers": [
            {
                "id": "api_football",
                "name": "API-Football",
                "description": "Football data including fixtures, stats, odds",
                "has_free_tier": True,
                "rate_limit": "100 requests/day",
            },
            {
                "id": "football_data",
                "name": "football-data.org",
                "description": "European leagues and competitions",
                "has_free_tier": True,
                "rate_limit": "10 requests/minute",
            },
            {
                "id": "odds_api",
                "name": "The Odds API",
                "description": "Historical and live odds",
                "has_free_tier": True,
                "rate_limit": "500 requests/month",
            },
        ]
    }


# Competitions
@router.get("/competitions")
async def get_competitions(db: AsyncSession = Depends(get_db)):
    """Get all competitions."""
    result = await db.execute(select(Competition).where(Competition.is_active == True))
    competitions = result.scalars().all()
    return {
        "competitions": [
            {
                "id": c.id,
                "name": c.name,
                "country": c.country,
                "logo_url": c.logo_url,
                "type": c.type,
                "current_season": c.current_season,
            }
            for c in competitions
        ]
    }


@router.get("/competitions/{competition_id}")
async def get_competition(competition_id: int, db: AsyncSession = Depends(get_db)):
    """Get competition details."""
    competition = await db.get(Competition, competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")

    # Get seasons
    seasons_result = await db.execute(
        select(Season).where(Season.competition_id == competition_id)
    )
    seasons = seasons_result.scalars().all()

    return {
        "id": competition.id,
        "name": competition.name,
        "country": competition.country,
        "logo_url": competition.logo_url,
        "type": competition.type,
        "current_season": competition.current_season,
        "seasons": [
            {
                "id": s.id,
                "year": s.year,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "is_current": s.is_current,
            }
            for s in seasons
        ],
    }


# Fixtures
@router.get("/fixtures")
async def get_fixtures(
    competition_id: Optional[int] = None,
    season: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Get fixtures with filters."""
    query = select(Fixture)

    if competition_id:
        # Need to join with season
        season_subq = select(Season.id).where(
            and_(Season.competition_id == competition_id)
        )
        if season:
            season_subq = season_subq.where(Season.year == season)
        query = query.where(Fixture.season_id.in_(season_subq))

    if date_from:
        query = query.where(Fixture.date >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(Fixture.date <= datetime.fromisoformat(date_to))
    if status:
        query = query.where(Fixture.status_short == status)

    query = query.order_by(Fixture.date).limit(limit).offset(offset)

    result = await db.execute(query)
    fixtures = result.scalars().all()

    # Load relationships
    fixture_ids = [f.id for f in fixtures]
    home_teams = {}
    away_teams = {}

    if fixture_ids:
        teams_result = await db.execute(
            select(Team).where(Team.id.in_(
                select(Fixture.home_team_id).where(Fixture.id.in_(fixture_ids))
            ).union(
                select(Fixture.away_team_id).where(Fixture.id.in_(fixture_ids))
            ))
        )
        for team in teams_result.scalars().all():
            home_teams[team.id] = team
            away_teams[team.id] = team

    return {
        "fixtures": [
            {
                "id": f.id,
                "date": f.date.isoformat() if f.date else None,
                "status": f.status_short,
                "status_long": f.status_long,
                "elapsed": f.status_elapsed,
                "round": f.round,
                "home_team": {
                    "id": home_teams.get(f.home_team_id, {}).id if f.home_team_id in home_teams else f.home_team_id,
                    "name": home_teams.get(f.home_team_id, {}).name if f.home_team_id in home_teams else "Unknown",
                    "logo_url": home_teams.get(f.home_team_id, {}).logo_url if f.home_team_id in home_teams else None,
                } if f.home_team_id in home_teams else {"id": f.home_team_id, "name": "Unknown"},
                "away_team": {
                    "id": away_teams.get(f.away_team_id, {}).id if f.away_team_id in away_teams else f.away_team_id,
                    "name": away_teams.get(f.away_team_id, {}).name if f.away_team_id in away_teams else "Unknown",
                    "logo_url": away_teams.get(f.away_team_id, {}).logo_url if f.away_team_id in away_teams else None,
                } if f.away_team_id in away_teams else {"id": f.away_team_id, "name": "Unknown"},
            }
            for f in fixtures
        ],
        "total": len(fixtures),
        "limit": limit,
        "offset": offset,
    }


@router.get("/fixtures/{fixture_id}")
async def get_fixture(fixture_id: int, db: AsyncSession = Depends(get_db)):
    """Get fixture details with events and statistics."""
    fixture = await db.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")

    # Get teams
    home_team = await db.get(Team, fixture.home_team_id)
    away_team = await db.get(Team, fixture.away_team_id)

    # Get events
    events_result = await db.execute(
        select(FixtureEvent).where(FixtureEvent.fixture_id == fixture_id)
    )
    events = events_result.scalars().all()

    # Get statistics
    stats_result = await db.execute(
        select(FixtureStatistics).where(FixtureStatistics.fixture_id == fixture_id)
    )
    statistics = stats_result.scalars().all()

    # Get lineups
    lineups_result = await db.execute(
        select(FixtureLineup).where(FixtureLineup.fixture_id == fixture_id)
    )
    lineups = lineups_result.scalars().all()

    # Get odds
    odds_result = await db.execute(
        select(FixtureOdds).where(FixtureOdds.fixture_id == fixture_id)
    )
    odds = odds_result.scalars().all()

    return {
        "id": fixture.id,
        "date": fixture.date.isoformat() if fixture.date else None,
        "timestamp": fixture.timestamp,
        "timezone": fixture.timezone,
        "status": fixture.status_short,
        "status_long": fixture.status_long,
        "elapsed": fixture.status_elapsed,
        "round": fixture.round,
        "home_team": {
            "id": home_team.id if home_team else fixture.home_team_id,
            "name": home_team.name if home_team else "Unknown",
            "logo_url": home_team.logo_url if home_team else None,
        },
        "away_team": {
            "id": away_team.id if away_team else fixture.away_team_id,
            "name": away_team.name if away_team else "Unknown",
            "logo_url": away_team.logo_url if away_team else None,
        },
        "events": [
            {
                "time": e.time_elapsed,
                "extra": e.time_extra,
                "type": e.type,
                "detail": e.detail,
                "team_id": e.team_id,
                "player_id": e.player_id,
            }
            for e in events
        ],
        "statistics": [
            {
                "team_id": s.team_id,
                "type": s.type,
                "value": s.value,
            }
            for s in statistics
        ],
        "lineups": [
            {
                "team_id": l.team_id,
                "player_id": l.player_id,
                "number": l.number,
                "position": l.position,
                "is_starting": l.is_starting,
            }
            for l in lineups
        ],
        "odds": [
            {
                "bookmaker_id": o.bookmaker_id,
                "market_type": o.market_type.value,
                "market_name": o.market_name,
                "value": o.value,
                "odd_home": o.odd_home,
                "odd_draw": o.odd_draw,
                "odd_away": o.odd_away,
                "is_live": o.is_live,
            }
            for o in odds
        ],
    }


# Sync
@router.post("/sync/competitions")
async def sync_competitions(
    provider: str = "api_football",
    db: AsyncSession = Depends(get_db),
):
    """Sync competitions from provider."""
    sync_service = SyncService(db)
    result = await sync_service.sync_competitions(provider)
    return result


@router.post("/sync/fixtures")
async def sync_fixtures(
    competition_id: int,
    season: int,
    days_ahead: int = 7,
    days_behind: int = 30,
    provider: str = "api_football",
    db: AsyncSession = Depends(get_db),
):
    """Sync fixtures for a competition."""
    sync_service = SyncService(db)
    result = await sync_service.sync_fixtures(
        competition_id, season, days_ahead, days_behind, provider
    )
    return result


@router.post("/sync/full")
async def full_sync(
    competition_ids: Optional[List[int]] = None,
    season: Optional[int] = None,
    days_ahead: int = 7,
    days_behind: int = 30,
    providers: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
):
    """Run full synchronization."""
    sync_service = SyncService(db)
    result = await sync_service.full_sync(
        competition_ids, season, days_ahead, days_behind, providers
    )
    return result


@router.get("/sync/logs")
async def get_sync_logs(
    provider: Optional[str] = None,
    operation: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get synchronization logs."""
    query = select(SyncLog).order_by(desc(SyncLog.started_at)).limit(limit)

    if provider:
        query = query.where(SyncLog.provider == provider)
    if operation:
        query = query.where(SyncLog.operation == operation)

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "logs": [
            {
                "id": log.id,
                "provider": log.provider,
                "operation": log.operation,
                "competition_id": log.competition_id,
                "season": log.season,
                "status": log.status,
                "records_processed": log.records_processed,
                "records_created": log.records_created,
                "records_updated": log.records_updated,
                "error_message": log.error_message,
                "started_at": log.started_at.isoformat(),
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            }
            for log in logs
        ]
    }


# Predictions
@router.get("/predictions/{fixture_id}")
async def get_predictions(fixture_id: int, db: AsyncSession = Depends(get_db)):
    """Get model predictions for a fixture."""
    fixture = await db.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")

    # Get latest model version
    model_result = await db.execute(
        select(ModelVersion).where(ModelVersion.is_active == True)
    )
    model = model_result.scalars().first()

    if not model:
        # Generate predictions on the fly
        return await generate_predictions(fixture_id, db)

    # Get stored predictions
    preds_result = await db.execute(
        select(ModelPrediction).where(
            and_(
                ModelPrediction.fixture_id == fixture_id,
                ModelPrediction.model_version_id == model.id,
            )
        )
    )
    predictions = preds_result.scalars().all()

    return {
        "fixture_id": fixture_id,
        "model_version": model.version,
        "predictions": [
            {
                "market_type": p.market_type.value,
                "market_line": p.market_line,
                "prob_home": p.prob_home,
                "prob_draw": p.prob_draw,
                "prob_away": p.prob_away,
                "prob_over": p.prob_over,
                "prob_under": p.prob_under,
                "prob_btts_yes": p.prob_bts_yes,
                "prob_btts_no": p.prob_bts_no,
                "edge_home": p.edge_home,
                "edge_draw": p.edge_draw,
                "edge_away": p.edge_away,
                "ev_home": p.ev_home,
                "ev_draw": p.ev_draw,
                "ev_away": p.ev_away,
                "confidence": p.confidence,
            }
            for p in predictions
        ],
    }


async def generate_predictions(fixture_id: int, db: AsyncSession) -> dict:
    """Generate predictions on the fly for a fixture."""
    fixture = await db.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")

    # Get historical data for model fitting
    # This is simplified - in production would use more data
    home_team_id = fixture.home_team_id
    away_team_id = fixture.away_team_id

    # Get past fixtures for both teams
    past_fixtures_result = await db.execute(
        select(Fixture).where(
            and_(
                Fixture.date < fixture.date,
                Fixture.status_short == "FT",
            )
        ).order_by(desc(Fixture.date)).limit(100)
    )
    past_fixtures = past_fixtures_result.scalars().all()

    # Prepare training data
    training_data = []
    team_ids = set()

    for f in past_fixtures:
        # Would need goals from events
        training_data.append({
            "home_team_id": f.home_team_id,
            "away_team_id": f.away_team_id,
            "home_goals": 0,  # Would calculate from events
            "away_goals": 0,
            "date": f.date,
        })
        team_ids.add(f.home_team_id)
        team_ids.add(f.away_team_id)

    team_ids.add(home_team_id)
    team_ids.add(away_team_id)

    # Fit and predict
    goals_model = CombinedGoalsModel()
    goals_model.fit(training_data, list(team_ids))
    goals_pred = goals_model.predict_match(home_team_id, away_team_id)

    # Corners
    corners_model = CornersModel()
    corners_model.fit(training_data, list(team_ids))
    corners_pred = corners_model.predict_match(home_team_id, away_team_id)

    # Cards
    cards_model = CardsModel()
    cards_model.fit(training_data, list(team_ids))
    cards_pred = cards_model.predict_match(home_team_id, away_team_id)

    return {
        "fixture_id": fixture_id,
        "model_version": "live_generated",
        "generated_at": datetime.utcnow().isoformat(),
        "goals": {
            "home_win": goals_pred.home_win_prob,
            "draw": goals_pred.draw_prob,
            "away_win": goals_pred.away_win_prob,
            "expected_goals_home": goals_pred.expected_goals_home,
            "expected_goals_away": goals_pred.expected_goals_away,
            "over_under": {str(k): {"over": v[0], "under": v[1]} for k, v in goals_pred.over_under_probs.items()},
            "btts": {"yes": goals_pred.btts_probs[0], "no": goals_pred.btts_probs[1]},
            "correct_scores": {f"{k[0]}-{k[1]}": v for k, v in list(goals_pred.correct_score_probs.items())[:10]},
        },
        "corners": {
            "home_mean": corners_pred.home_corners_mean,
            "away_mean": corners_pred.away_corners_mean,
            "total_mean": corners_pred.total_corners_mean,
            "over_under": {str(k): {"over": v[0], "under": v[1]} for k, v in corners_pred.over_under_probs.items()},
            "handicap": {str(k): {"home": v[0], "away": v[1]} for k, v in corners_pred.handicap_probs.items()},
        },
        "cards": {
            "home_mean": cards_pred.home_cards_mean,
            "away_mean": cards_pred.away_cards_mean,
            "total_mean": cards_pred.total_cards_mean,
            "over_under": {str(k): {"over": v[0], "under": v[1]} for k, v in cards_pred.over_under_probs.items()},
            "handicap": {str(k): {"home": v[0], "away": v[1]} for k, v in cards_pred.handicap_probs.items()},
            "red_card_prob": {"home": cards_pred.red_card_prob_home, "away": cards_pred.red_card_prob_away},
        },
    }


# Value Bets
@router.get("/value-bets")
async def get_value_bets(
    fixture_id: Optional[int] = None,
    min_ev: float = 0.05,
    min_edge: float = 0.02,
    db: AsyncSession = Depends(get_db),
):
    """Get value betting opportunities."""
    # Get fixtures to analyze
    if fixture_id:
        fixtures = [await db.get(Fixture, fixture_id)]
        if not fixtures[0]:
            raise HTTPException(status_code=404, detail="Fixture not found")
    else:
        # Get upcoming fixtures
        now = datetime.utcnow()
        fixtures_result = await db.execute(
            select(Fixture).where(
                and_(
                    Fixture.date >= now,
                    Fixture.date <= now + timedelta(days=3),
                    Fixture.status_short.in_(["NS", "TBD"]),
                )
            ).limit(20)
        )
        fixtures = fixtures_result.scalars().all()

    all_value_bets = []
    engine = ValueBettingEngine()

    for fixture in fixtures:
        # Get predictions
        pred_response = await get_predictions(fixture.id, db)
        predictions = pred_response.get("predictions", [])

        if not predictions:
            continue

        # Get odds
        odds_result = await db.execute(
            select(FixtureOdds).where(FixtureOdds.fixture_id == fixture.id)
        )
        odds_list = odds_result.scalars().all()

        # Convert to model probabilities
        # Simplified - would use actual predictions
        model_probs = ModelProbabilities(
            fixture_id=fixture.id,
            model_version="combined",
            prob_home=0.45,
            prob_draw=0.28,
            prob_away=0.27,
            prob_over={2.5: 0.52},
            prob_under={2.5: 0.48},
            prob_btts_yes=0.55,
            prob_btts_no=0.45,
            prob_over_corners={9.5: 0.58},
            prob_over_cards={4.5: 0.53},
            confidence=0.7,
            data_quality=0.8,
        )

        # Convert odds
        odds_data = []
        for o in odds_list:
            odds_data.append(OddsData(
                market_type=o.market_type.value,
                market_line=o.value,
                bookmaker_id=o.bookmaker_id,
                bookmaker_name="",  # Would lookup
                odd_home=o.odd_home,
                odd_draw=o.odd_draw,
                odd_away=o.odd_away,
                odd_over=o.odd_home if o.market_type == MarketType.OVER_UNDER else None,
                odd_under=o.odd_away if o.market_type == MarketType.OVER_UNDER else None,
                odd_btts_yes=o.odd_home if o.market_type == MarketType.BOTH_TEAMS_SCORE else None,
                odd_btts_no=o.odd_away if o.market_type == MarketType.BOTH_TEAMS_SCORE else None,
                odd_handicap=o.odd_handicap,
                timestamp=o.last_update or o.created_at,
                is_live=o.is_live,
            ))

        value_bets = engine.find_all_value_bets(odds_data, model_probs)

        for vb in value_bets:
            if vb.expected_value >= min_ev and vb.edge >= min_edge:
                all_value_bets.append({
                    "fixture_id": vb.fixture_id,
                    "selection": vb.selection.value,
                    "market_type": vb.market_type,
                    "market_line": vb.market_line,
                    "model_probability": vb.model_probability,
                    "implied_probability": vb.implied_probability,
                    "edge": vb.edge,
                    "expected_value": vb.expected_value,
                    "odd": vb.odd,
                    "bookmaker": vb.bookmaker_name,
                    "confidence": vb.confidence,
                    "kelly_stake": vb.kelly_stake,
                    "fractional_kelly_stake": vb.fractional_kelly_stake,
                    "is_live": vb.is_live,
                })

    # Sort by EV
    all_value_bets.sort(key=lambda x: x["expected_value"], reverse=True)

    return {
        "value_bets": all_value_bets,
        "count": len(all_value_bets),
        "generated_at": datetime.utcnow().isoformat(),
    }


# Live
@router.get("/live/{fixture_id}")
async def get_live_analysis(fixture_id: int, db: AsyncSession = Depends(get_db)):
    """Get live analysis for a fixture."""
    fixture = await db.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")

    # Get events and statistics
    events_result = await db.execute(
        select(FixtureEvent).where(FixtureEvent.fixture_id == fixture_id)
    )
    events = events_result.scalars().all()

    stats_result = await db.execute(
        select(FixtureStatistics).where(FixtureStatistics.fixture_id == fixture_id)
    )
    statistics = stats_result.scalars().all()

    # Get current minute from fixture status
    current_minute = fixture.status_elapsed or 0
    added_time = 0  # Would parse from status

    # Create live state
    live_state = create_live_state_from_events(
        fixture_id, events, statistics, current_minute, added_time
    )

    # Get pre-match predictions for initialization
    pred_response = await get_predictions(fixture_id, db)
    predictions = pred_response.get("predictions", [])

    # Initialize live model
    live_model = LiveModel()
    if predictions:
        # Use first prediction for initialization
        p = predictions[0]
        live_model.initialize_from_pre_match(
            p.get("prob_home", 0.45),
            p.get("prob_draw", 0.28),
            p.get("prob_away", 0.27),
            p.get("expected_goals_home", 1.4),
            p.get("expected_goals_away", 1.1),
        )

    live_pred = live_model.update(live_state)

    return {
        "fixture_id": fixture_id,
        "match_state": {
            "minute": live_state.minute,
            "added_time": live_state.added_time,
            "state": live_state.state.value,
            "home_score": live_state.home_score,
            "away_score": live_state.away_score,
            "home_shots": live_state.home_shots,
            "away_shots": live_state.away_shots,
            "home_corners": live_state.home_corners,
            "away_corners": live_state.away_corners,
            "home_yellow_cards": live_state.home_yellow_cards,
            "away_yellow_cards": live_state.away_yellow_cards,
            "home_red_cards": live_state.home_red_cards,
            "away_red_cards": live_state.away_red_cards,
            "home_xg": live_state.home_xg,
            "away_xg": live_state.away_xg,
            "pressure_index": live_state.pressure_index,
        },
        "predictions": {
            "home_win": live_pred.home_win_prob,
            "draw": live_pred.draw_prob,
            "away_win": live_pred.away_win_prob,
            "total_goals_expected": live_pred.total_goals_expected,
            "next_goal": live_pred.next_goal_probability,
            "over_under_live": {str(k): {"over": v[0], "under": v[1]} for k, v in live_pred.over_under_live.items()},
            "time_to_next_goal": live_pred.time_to_next_goal,
        },
    }


# Backtesting
@router.post("/backtest")
async def run_backtest(
    model_version_id: int,
    start_date: str,
    end_date: str,
    competition_ids: List[int],
    markets: List[str],
    min_edge: float = 0.02,
    min_confidence: float = 0.6,
    stake_strategy: str = "fractional_kelly",
    kelly_fraction: float = 0.25,
    db: AsyncSession = Depends(get_db),
):
    """Run backtest simulation."""
    # This would be a long-running task, simplified here
    return {
        "message": "Backtest started",
        "backtest_id": 1,
        "status": "running",
    }


@router.get("/backtest/{backtest_id}")
async def get_backtest_results(backtest_id: int, db: AsyncSession = Depends(get_db)):
    """Get backtest results."""
    # Placeholder
    return {
        "backtest_id": backtest_id,
        "status": "completed",
        "results": {},
    }