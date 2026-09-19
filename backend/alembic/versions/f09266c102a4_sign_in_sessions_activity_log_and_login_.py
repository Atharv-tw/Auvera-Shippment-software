"""sign-in sessions, activity log and login lockout

Three things arrive together because they are one change.

``user_sessions`` is the live state behind a refresh token: it is what makes a
sign-out mean something, where before a token stayed valid until it expired and
nothing could call it back.

``auth_events`` is the append-only record the CEO and admins read - who signed
in, who signed out, when. It is deliberately a second table rather than a column
on the first: signing out everywhere revokes several sessions but is one line of
history, and spent sessions can one day be swept up without the record going
with them. Its ``session_id`` is a plain integer for that reason, not a foreign
key.

``users`` gains a failed-attempt counter and a lock expiry, so guessing a
password stops being unlimited. Those two are state rather than history, and
stay out of the activity feed on purpose - a wall of failed attempts would bury
the sign-ins it exists to show.

Revision ID: f09266c102a4
Revises: a7c41d0be55f
Create Date: 2026-09-19 12:32:35.526215

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f09266c102a4'
down_revision: Union[str, Sequence[str], None] = 'a7c41d0be55f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the two session tables and the lockout columns."""
    op.create_table('auth_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('user_email', sa.String(length=255), nullable=True),
    sa.Column('user_name', sa.String(length=255), nullable=True),
    sa.Column('event', sa.String(length=20), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_auth_events_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_events'))
    )
    with op.batch_alter_table('auth_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_auth_events_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_auth_events_event'), ['event'], unique=False)
        batch_op.create_index(batch_op.f('ix_auth_events_user_id'), ['user_id'], unique=False)

    op.create_table('user_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('refresh_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.Column('revoked_reason', sa.String(length=20), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_sessions_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_sessions'))
    )
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_sessions_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_sessions_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('failed_login_count', sa.Integer(), nullable=False, server_default='0')
        )
        batch_op.add_column(sa.Column('locked_until', sa.DateTime(), nullable=True))



def downgrade() -> None:
    """Drop them again; no data is carried anywhere else."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('locked_until')
        batch_op.drop_column('failed_login_count')

    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_sessions_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_sessions_expires_at'))

    op.drop_table('user_sessions')
    with op.batch_alter_table('auth_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_auth_events_user_id'))
        batch_op.drop_index(batch_op.f('ix_auth_events_event'))
        batch_op.drop_index(batch_op.f('ix_auth_events_created_at'))

    op.drop_table('auth_events')
