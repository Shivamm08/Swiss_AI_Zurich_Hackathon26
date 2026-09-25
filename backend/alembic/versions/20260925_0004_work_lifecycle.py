"""work lifecycle: ticket work status, specialist resolution, roles admin/analyst/specialist

Revision ID: 0004_work_lifecycle
Revises: 0003_messaging
Create Date: 2026-09-25 09:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0004_work_lifecycle'
down_revision: Union[str, None] = '0003_messaging'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive and idempotent, like the earlier migrations (the Supabase database is shared).
    op.add_column('tickets', sa.Column('work_status', sa.String(length=20), server_default='open', nullable=False), if_not_exists=True)
    op.add_column('tickets', sa.Column('resolution', sa.String(length=30), nullable=True), if_not_exists=True)
    op.add_column('tickets', sa.Column('resolution_comment', sa.Text(), nullable=True), if_not_exists=True)
    op.add_column('tickets', sa.Column('resolved_by', sa.String(length=120), nullable=True), if_not_exists=True)
    op.add_column('tickets', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True), if_not_exists=True)
    op.add_column('tickets', sa.Column('activity', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False), if_not_exists=True)
    op.create_index(op.f('ix_tickets_work_status'), 'tickets', ['work_status'], unique=False, if_not_exists=True)

    # Backfill: closed tickets are done; approved tickets with an assignee are with a specialist;
    # everything else waits for an analyst. tickets.assignee itself is never cleared here: on the
    # shared Supabase that column also belongs to a teammate's branch.
    op.execute("""
        UPDATE tickets SET work_status = CASE
            WHEN status = 'done' THEN 'done'
            WHEN assignee IS NOT NULL AND triage_state IN ('approved', 'edited') THEN 'assigned'
            ELSE 'open' END
        WHERE work_status = 'open'
    """)
    # Roles: team leads become 'analyst' (Team Lead / Analyst), everyone else who works tickets becomes 'specialist'.
    op.alter_column('users', 'role', server_default='specialist')
    op.execute("""
        UPDATE users SET role = CASE role WHEN 'lead' THEN 'analyst' WHEN 'analyst' THEN 'specialist' ELSE role END
        WHERE role IN ('lead', 'analyst') AND NOT EXISTS (SELECT 1 FROM users WHERE role = 'specialist')
    """)


def downgrade() -> None:
    op.alter_column('users', 'role', server_default='analyst')
    op.execute("UPDATE users SET role = CASE role WHEN 'analyst' THEN 'lead' WHEN 'specialist' THEN 'analyst' ELSE role END")
    op.drop_index(op.f('ix_tickets_work_status'), table_name='tickets')
    for column in ('activity', 'resolved_at', 'resolved_by', 'resolution_comment', 'resolution', 'work_status'):
        op.drop_column('tickets', column)
