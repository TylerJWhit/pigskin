"""add_real_auction_tables_issue_194

Revision ID: a1b2c3d4e5f6
Revises: 7679204de4ae
Create Date: 2026-05-01 10:00:00.000000

Adds three tables to support real Sleeper auction draft ingestion and corpus
management (issue #194, ADR-004, ADR-005).

Tables added:
  - real_auction_drafts  — one row per Sleeper draft ingested
  - real_auction_picks   — one row per pick within a draft
  - auction_corpus       — corpus membership/quality record for each draft

Indexes added:
  - idx_rad_season       — real_auction_drafts(season)
  - idx_rap_draft_id     — real_auction_picks(draft_id)
  - idx_rap_player_id    — real_auction_picks(sleeper_player_id)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7679204de4ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # real_auction_drafts
    # ------------------------------------------------------------------
    op.create_table(
        'real_auction_drafts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('sleeper_draft_id', sa.Text(), nullable=False, unique=True),
        sa.Column('sleeper_league_id', sa.Text(), nullable=False),
        sa.Column('season', sa.Text(), nullable=False),
        sa.Column('team_count', sa.Integer(), nullable=False),
        sa.Column('scoring_format', sa.Text(), nullable=True),
        sa.Column('auction_budget', sa.Integer(), nullable=True),
        sa.Column('draft_date', sa.DateTime(), nullable=True),
        sa.Column(
            'fetched_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column('raw_metadata', sa.Text(), nullable=True),
    )
    op.create_index(
        'idx_rad_season',
        'real_auction_drafts',
        ['season'],
    )

    # ------------------------------------------------------------------
    # real_auction_picks
    # ------------------------------------------------------------------
    op.create_table(
        'real_auction_picks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'draft_id',
            sa.Integer(),
            sa.ForeignKey('real_auction_drafts.id'),
            nullable=False,
        ),
        sa.Column('sleeper_player_id', sa.Text(), nullable=False),
        sa.Column('player_name', sa.Text(), nullable=False),
        sa.Column('position', sa.Text(), nullable=False),
        sa.Column('nfl_team', sa.Text(), nullable=True),
        sa.Column('winner_bid', sa.Integer(), nullable=False),
        sa.Column('picked_by_slot', sa.Integer(), nullable=True),
        sa.Column('pick_order', sa.Integer(), nullable=True),
        sa.Column('raw_pick', sa.Text(), nullable=True),
    )
    op.create_index(
        'idx_rap_draft_id',
        'real_auction_picks',
        ['draft_id'],
    )
    op.create_index(
        'idx_rap_player_id',
        'real_auction_picks',
        ['sleeper_player_id'],
    )

    # ------------------------------------------------------------------
    # auction_corpus
    # ------------------------------------------------------------------
    op.create_table(
        'auction_corpus',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'draft_id',
            sa.Integer(),
            sa.ForeignKey('real_auction_drafts.id'),
            nullable=False,
            unique=True,
        ),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column(
            'used_in_backtest',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('0'),
        ),
        sa.Column('exclusion_reason', sa.Text(), nullable=True),
        sa.Column('included_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('auction_corpus')
    op.drop_index('idx_rap_player_id', table_name='real_auction_picks')
    op.drop_index('idx_rap_draft_id', table_name='real_auction_picks')
    op.drop_table('real_auction_picks')
    op.drop_index('idx_rad_season', table_name='real_auction_drafts')
    op.drop_table('real_auction_drafts')
