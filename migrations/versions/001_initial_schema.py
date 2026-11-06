"""Initial schema migration.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    market_type_enum = sa.Enum(
        'match_winner', 'over_under', 'both_teams_score',
        'asian_handicap', 'corners', 'cards',
        'correct_score', 'half_time_full_time',
        'double_chance', 'draw_no_bet',
        name='markettype'
    )
    market_type_enum.create(op.get_bind())

    # competitions
    op.create_table(
        'competitions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('type', sa.String(50), nullable=True),
        sa.Column('current_season', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # seasons
    op.create_table(
        'seasons',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competitions.id'), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_current', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('competition_id', 'year', name='uq_competition_year'),
    )
    op.create_index('ix_seasons_competition_id', 'seasons', ['competition_id'])

    # teams
    op.create_table(
        'teams',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('short_name', sa.String(50), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('venue_name', sa.String(200), nullable=True),
        sa.Column('venue_city', sa.String(100), nullable=True),
        sa.Column('venue_capacity', sa.Integer(), nullable=True),
        sa.Column('founded', sa.Integer(), nullable=True),
        sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competitions.id'), nullable=True),
        sa.Column('is_national', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_teams_competition_id', 'teams', ['competition_id'])
    op.create_index('ix_teams_country', 'teams', ['country'])

    # fixtures
    op.create_table(
        'fixtures',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('seasons.id'), nullable=False),
        sa.Column('home_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('away_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('timestamp', sa.Integer(), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.Column('venue_id', sa.Integer(), nullable=True),
        sa.Column('referee_id', sa.Integer(), nullable=True),
        sa.Column('status_short', sa.String(10), nullable=True),
        sa.Column('status_long', sa.String(50), nullable=True),
        sa.Column('status_elapsed', sa.Integer(), nullable=True),
        sa.Column('round', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_fixtures_season_id', 'fixtures', ['season_id'])
    op.create_index('ix_fixtures_date', 'fixtures', ['date'])
    op.create_index('ix_fixtures_home_team_id', 'fixtures', ['home_team_id'])
    op.create_index('ix_fixtures_away_team_id', 'fixtures', ['away_team_id'])
    op.create_index('ix_fixtures_status', 'fixtures', ['status_short'])

    # referees
    op.create_table(
        'referees',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('photo_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # fixture_events
    op.create_table(
        'fixture_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('fixture_id', sa.Integer(), sa.ForeignKey('fixtures.id'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=True),
        sa.Column('time_elapsed', sa.Integer(), nullable=True),
        sa.Column('time_extra', sa.Integer(), nullable=True),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('detail', sa.String(100), nullable=True),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_fixture_events_fixture_id', 'fixture_events', ['fixture_id'])
    op.create_index('ix_fixture_events_team_id', 'fixture_events', ['team_id'])

    # fixture_statistics
    op.create_table(
        'fixture_statistics',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('fixture_id', sa.Integer(), sa.ForeignKey('fixtures.id'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('value', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_fixture_stats_fixture_team_type', 'fixture_statistics', ['fixture_id', 'team_id', 'type'])

    # fixture_lineups
    op.create_table(
        'fixture_lineups',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('fixture_id', sa.Integer(), sa.ForeignKey('fixtures.id'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('formation', sa.String(20), nullable=True),
        sa.Column('is_starting', sa.Boolean(), default=True),
        sa.Column('player_id', sa.Integer(), nullable=True),
        sa.Column('number', sa.Integer(), nullable=True),
        sa.Column('position', sa.String(20), nullable=True),
        sa.Column('grid', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_fixture_lineups_fixture_id', 'fixture_lineups', ['fixture_id'])

    # players
    op.create_table(
        'players',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('firstname', sa.String(100), nullable=True),
        sa.Column('lastname', sa.String(100), nullable=True),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('birth_place', sa.String(200), nullable=True),
        sa.Column('birth_country', sa.String(100), nullable=True),
        sa.Column('nationality', sa.String(100), nullable=True),
        sa.Column('height', sa.String(20), nullable=True),
        sa.Column('weight', sa.String(20), nullable=True),
        sa.Column('photo_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # player_statistics
    op.create_table(
        'player_statistics',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('player_id', sa.Integer(), sa.ForeignKey('players.id'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('seasons.id'), nullable=False),
        sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competitions.id'), nullable=False),
        sa.Column('appearances', sa.Integer(), default=0),
        sa.Column('minutes_played', sa.Integer(), default=0),
        sa.Column('goals', sa.Integer(), default=0),
        sa.Column('assists', sa.Integer(), default=0),
        sa.Column('yellow_cards', sa.Integer(), default=0),
        sa.Column('red_cards', sa.Integer(), default=0),
        sa.Column('shots_total', sa.Integer(), default=0),
        sa.Column('shots_on_target', sa.Integer(), default=0),
        sa.Column('passes_total', sa.Integer(), default=0),
        sa.Column('passes_accuracy', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_player_stats_player_season', 'player_statistics', ['player_id', 'season_id'])

    # referee_statistics
    op.create_table(
        'referee_statistics',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('referee_id', sa.Integer(), sa.ForeignKey('referees.id'), nullable=False),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('seasons.id'), nullable=False),
        sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competitions.id'), nullable=False),
        sa.Column('matches', sa.Integer(), default=0),
        sa.Column('yellow_cards_per_game', sa.Float(), nullable=True),
        sa.Column('red_cards_per_game', sa.Float(), nullable=True),
        sa.Column('penalties_per_game', sa.Float(), nullable=True),
        sa.Column('home_wins', sa.Integer(), default=0),
        sa.Column('draws', sa.Integer(), default=0),
        sa.Column('away_wins', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # team_statistics
    op.create_table(
        'team_statistics',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('season_id', sa.Integer(), sa.ForeignKey('seasons.id'), nullable=False),
        sa.Column('competition_id', sa.Integer(), sa.ForeignKey('competitions.id'), nullable=False),
        sa.Column('form', sa.String(50), nullable=True),
        sa.Column('played', sa.Integer(), default=0),
        sa.Column('wins', sa.Integer(), default=0),
        sa.Column('draws', sa.Integer(), default=0),
        sa.Column('losses', sa.Integer(), default=0),
        sa.Column('goals_for', sa.Integer(), default=0),
        sa.Column('goals_against', sa.Integer(), default=0),
        sa.Column('goals_for_home', sa.Integer(), default=0),
        sa.Column('goals_against_home', sa.Integer(), default=0),
        sa.Column('goals_for_away', sa.Integer(), default=0),
        sa.Column('goals_against_away', sa.Integer(), default=0),
        sa.Column('clean_sheets', sa.Integer(), default=0),
        sa.Column('clean_sheets_home', sa.Integer(), default=0),
        sa.Column('clean_sheets_away', sa.Integer(), default=0),
        sa.Column('failed_to_score', sa.Integer(), default=0),
        sa.Column('failed_to_score_home', sa.Integer(), default=0),
        sa.Column('failed_to_score_away', sa.Integer(), default=0),
        sa.Column('penalties_scored', sa.Integer(), default=0),
        sa.Column('penalties_missed', sa.Integer(), default=0),
        sa.Column('yellow_cards', sa.Integer(), default=0),
        sa.Column('red_cards', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('team_id', 'season_id', name='uq_team_season'),
    )
    op.create_index('ix_team_stats_team_season', 'team_statistics', ['team_id', 'season_id'])

    # bookmakers
    op.create_table(
        'bookmakers',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # fixture_odds
    op.create_table(
        'fixture_odds',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('fixture_id', sa.Integer(), sa.ForeignKey('fixtures.id'), nullable=False),
        sa.Column('bookmaker_id', sa.Integer(), sa.ForeignKey('bookmakers.id'), nullable=False),
        sa.Column('market_type', market_type_enum, nullable=False),
        sa.Column('market_name', sa.String(100), nullable=True),
        sa.Column('value', sa.String(50), nullable=True),
        sa.Column('odd_home', sa.Float(), nullable=True),
        sa.Column('odd_draw', sa.Float(), nullable=True),
        sa.Column('odd_away', sa.Float(), nullable=True),
        sa.Column('odd_handicap', sa.Float(), nullable=True),
        sa.Column('is_live', sa.Boolean(), default=False),
        sa.Column('last_update', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_fixture_odds_fixture_market', 'fixture_odds', ['fixture_id', 'market_type', 'bookmaker_id'])
    op.create_index('ix_fixture_odds_live', 'fixture_odds', ['is_live', 'last_update'])

    # model_versions
    op.create_table(
        'model_versions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parameters', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('name', 'version', name='uq_model_version'),
    )

    # model_predictions
    op.create_table(
        'model_predictions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('fixture_id', sa.Integer(), sa.ForeignKey('fixtures.id'), nullable=False),
        sa.Column('model_version_id', sa.Integer(), sa.ForeignKey('model_versions.id'), nullable=False),
        sa.Column('market_type', market_type_enum, nullable=False),
        sa.Column('market_line', sa.String(50), nullable=True),
        sa.Column('prob_home', sa.Float(), nullable=True),
        sa.Column('prob_draw', sa.Float(), nullable=True),
        sa.Column('prob_away', sa.Float(), nullable=True),
        sa.Column('prob_over', sa.Float(), nullable=True),
        sa.Column('prob_under', sa.Float(), nullable=True),
        sa.Column('prob_bts_yes', sa.Float(), nullable=True),
        sa.Column('prob_bts_no', sa.Float(), nullable=True),
        sa.Column('edge_home', sa.Float(), nullable=True),
        sa.Column('edge_draw', sa.Float(), nullable=True),
        sa.Column('edge_away', sa.Float(), nullable=True),
        sa.Column('edge_over', sa.Float(), nullable=True),
        sa.Column('edge_under', sa.Float(), nullable=True),
        sa.Column('edge_bts_yes', sa.Float(), nullable=True),
        sa.Column('edge_bts_no', sa.Float(), nullable=True),
        sa.Column('ev_home', sa.Float(), nullable=True),
        sa.Column('ev_draw', sa.Float(), nullable=True),
        sa.Column('ev_away', sa.Float(), nullable=True),
        sa.Column('ev_over', sa.Float(), nullable=True),
        sa.Column('ev_under', sa.Float(), nullable=True),
        sa.Column('ev_bts_yes', sa.Float(), nullable=True),
        sa.Column('ev_bts_no', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('data_quality_score', sa.Float(), nullable=True),
        sa.Column('prediction_time', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_predictions_fixture_model_market', 'model_predictions', ['fixture_id', 'model_version_id', 'market_type'])
    op.create_index('ix_predictions_edge', 'model_predictions', ['edge_home', 'edge_draw', 'edge_away'])

    # prediction_results
    op.create_table(
        'prediction_results',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('prediction_id', sa.Integer(), sa.ForeignKey('model_predictions.id'), nullable=False),
        sa.Column('fixture_id', sa.Integer(), sa.ForeignKey('fixtures.id'), nullable=False),
        sa.Column('result_home', sa.Integer(), nullable=True),
        sa.Column('result_draw', sa.Integer(), nullable=True),
        sa.Column('result_away', sa.Integer(), nullable=True),
        sa.Column('result_over', sa.Integer(), nullable=True),
        sa.Column('result_under', sa.Integer(), nullable=True),
        sa.Column('result_bts_yes', sa.Integer(), nullable=True),
        sa.Column('result_bts_no', sa.Integer(), nullable=True),
        sa.Column('result_corners_over', sa.Integer(), nullable=True),
        sa.Column('result_cards_over', sa.Integer(), nullable=True),
        sa.Column('is_correct_home', sa.Boolean(), nullable=True),
        sa.Column('is_correct_draw', sa.Boolean(), nullable=True),
        sa.Column('is_correct_away', sa.Boolean(), nullable=True),
        sa.Column('is_correct_over', sa.Boolean(), nullable=True),
        sa.Column('is_correct_under', sa.Boolean(), nullable=True),
        sa.Column('is_correct_bts', sa.Boolean(), nullable=True),
        sa.Column('brier_score', sa.Float(), nullable=True),
        sa.Column('log_loss', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # backtest_runs
    op.create_table(
        'backtest_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('model_version_id', sa.Integer(), sa.ForeignKey('model_versions.id'), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('competitions', postgresql.JSONB(), nullable=True),
        sa.Column('markets', postgresql.JSONB(), nullable=True),
        sa.Column('min_edge', sa.Float(), nullable=True),
        sa.Column('min_confidence', sa.Float(), nullable=True),
        sa.Column('stake_strategy', sa.String(50), nullable=True),
        sa.Column('kelly_fraction', sa.Float(), nullable=True),
        sa.Column('total_bets', sa.Integer(), default=0),
        sa.Column('winning_bets', sa.Integer(), default=0),
        sa.Column('total_stake', sa.Float(), default=0.0),
        sa.Column('total_return', sa.Float(), default=0.0),
        sa.Column('roi', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.Column('yield_percent', sa.Float(), nullable=True),
        sa.Column('clv', sa.Float(), nullable=True),
        sa.Column('brier_score', sa.Float(), nullable=True),
        sa.Column('log_loss', sa.Float(), nullable=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )

    # backtest_bets
    op.create_table(
        'backtest_bets',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('backtest_run_id', sa.Integer(), sa.ForeignKey('backtest_runs.id'), nullable=False),
        sa.Column('fixture_id', sa.Integer(), sa.ForeignKey('fixtures.id'), nullable=False),
        sa.Column('prediction_id', sa.Integer(), sa.ForeignKey('model_predictions.id'), nullable=True),
        sa.Column('market_type', market_type_enum, nullable=False),
        sa.Column('market_line', sa.String(50), nullable=True),
        sa.Column('selection', sa.String(20), nullable=False),
        sa.Column('odd', sa.Float(), nullable=False),
        sa.Column('prob_model', sa.Float(), nullable=False),
        sa.Column('prob_implied', sa.Float(), nullable=False),
        sa.Column('edge', sa.Float(), nullable=False),
        sa.Column('ev', sa.Float(), nullable=False),
        sa.Column('stake', sa.Float(), nullable=False),
        sa.Column('result', sa.String(20), nullable=True),
        sa.Column('profit', sa.Float(), nullable=True),
        sa.Column('bankroll_before', sa.Float(), nullable=True),
        sa.Column('bankroll_after', sa.Float(), nullable=True),
        sa.Column('bet_time', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # sync_logs
    op.create_table(
        'sync_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('operation', sa.String(50), nullable=False),
        sa.Column('competition_id', sa.Integer(), nullable=True),
        sa.Column('season', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('records_processed', sa.Integer(), default=0),
        sa.Column('records_created', sa.Integer(), default=0),
        sa.Column('records_updated', sa.Integer(), default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_sync_logs_provider_operation', 'sync_logs', ['provider', 'operation', 'started_at'])

    # bankroll_simulations
    op.create_table(
        'bankroll_simulations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('initial_bankroll', sa.Float(), nullable=False),
        sa.Column('current_bankroll', sa.Float(), nullable=False),
        sa.Column('peak_bankroll', sa.Float(), nullable=False),
        sa.Column('max_drawdown', sa.Float(), default=0.0),
        sa.Column('max_drawdown_percent', sa.Float(), default=0.0),
        sa.Column('total_bets', sa.Integer(), default=0),
        sa.Column('winning_bets', sa.Integer(), default=0),
        sa.Column('roi', sa.Float(), nullable=True),
        sa.Column('kelly_fraction', sa.Float(), nullable=True),
        sa.Column('min_edge', sa.Float(), nullable=True),
        sa.Column('min_confidence', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # bankroll_bets
    op.create_table(
        'bankroll_bets',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('simulation_id', sa.Integer(), sa.ForeignKey('bankroll_simulations.id'), nullable=False),
        sa.Column('fixture_id', sa.Integer(), sa.ForeignKey('fixtures.id'), nullable=True),
        sa.Column('market_type', market_type_enum, nullable=False),
        sa.Column('market_line', sa.String(50), nullable=True),
        sa.Column('selection', sa.String(20), nullable=False),
        sa.Column('odd', sa.Float(), nullable=False),
        sa.Column('stake', sa.Float(), nullable=False),
        sa.Column('unit_size', sa.Float(), nullable=True),
        sa.Column('result', sa.String(20), nullable=True),
        sa.Column('profit', sa.Float(), nullable=True),
        sa.Column('bankroll_before', sa.Float(), nullable=False),
        sa.Column('bankroll_after', sa.Float(), nullable=False),
        sa.Column('bet_date', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('bankroll_bets')
    op.drop_table('bankroll_simulations')
    op.drop_table('sync_logs')
    op.drop_table('backtest_bets')
    op.drop_table('backtest_runs')
    op.drop_table('prediction_results')
    op.drop_table('model_predictions')
    op.drop_table('model_versions')
    op.drop_table('fixture_odds')
    op.drop_table('bookmakers')
    op.drop_table('team_statistics')
    op.drop_table('referee_statistics')
    op.drop_table('player_statistics')
    op.drop_table('players')
    op.drop_table('fixture_lineups')
    op.drop_table('fixture_statistics')
    op.drop_table('fixture_events')
    op.drop_table('referees')
    op.drop_table('fixtures')
    op.drop_table('teams')
    op.drop_table('seasons')
    op.drop_table('competitions')

    # Drop enum
    sa.Enum(name='markettype').drop(op.get_bind())