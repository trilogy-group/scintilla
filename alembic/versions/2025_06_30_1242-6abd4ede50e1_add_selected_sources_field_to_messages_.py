"""add_selected_sources_field_to_messages_table

Revision ID: 6abd4ede50e1
Revises: 372d38a7dbe5
Create Date: 2025-06-30 12:42:45.469621

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '6abd4ede50e1'
down_revision = '372d38a7dbe5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add selected_sources field to messages table
    op.add_column('messages', 
        sa.Column('selected_sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    # Remove selected_sources field from messages table
    op.drop_column('messages', 'selected_sources') 