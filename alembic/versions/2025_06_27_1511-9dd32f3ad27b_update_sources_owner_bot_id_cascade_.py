"""update_sources_owner_bot_id_cascade_delete

Revision ID: 9dd32f3ad27b
Revises: 06401631d456
Create Date: 2025-06-27 15:11:01.636312

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9dd32f3ad27b'
down_revision = '06401631d456'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing foreign key constraint
    op.drop_constraint('sources_owner_bot_id_fkey', 'sources', type_='foreignkey')
    
    # Recreate the foreign key constraint with CASCADE DELETE
    op.create_foreign_key(
        'sources_owner_bot_id_fkey',
        'sources', 'bots',
        ['owner_bot_id'], ['bot_id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Drop the CASCADE foreign key constraint
    op.drop_constraint('sources_owner_bot_id_fkey', 'sources', type_='foreignkey')
    
    # Recreate the original foreign key constraint with NO ACTION
    op.create_foreign_key(
        'sources_owner_bot_id_fkey',
        'sources', 'bots',
        ['owner_bot_id'], ['bot_id']
    ) 