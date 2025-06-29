"""fix cascade delete constraints

Revision ID: d617f8eb2ccb
Revises: 2025_06_29_1702-fresh_initial_migration
Create Date: 2025-06-29 18:13:23.123456

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd617f8eb2ccb'
down_revision = '203ced341cf3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix sources.owner_bot_id foreign key constraint
    op.drop_constraint('sources_owner_bot_id_fkey', 'sources', type_='foreignkey')
    op.create_foreign_key(
        'sources_owner_bot_id_fkey',
        'sources', 'bots',
        ['owner_bot_id'], ['bot_id'],
        ondelete='CASCADE'
    )
    
    # Fix source_tools.source_id foreign key constraint
    op.drop_constraint('source_tools_source_id_fkey', 'source_tools', type_='foreignkey')
    op.create_foreign_key(
        'source_tools_source_id_fkey',
        'source_tools', 'sources',
        ['source_id'], ['source_id'],
        ondelete='CASCADE'
    )
    
    # Fix bot_source_associations foreign key constraints
    op.drop_constraint('bot_source_associations_bot_id_fkey', 'bot_source_associations', type_='foreignkey')
    op.create_foreign_key(
        'bot_source_associations_bot_id_fkey',
        'bot_source_associations', 'bots',
        ['bot_id'], ['bot_id'],
        ondelete='CASCADE'
    )
    
    op.drop_constraint('bot_source_associations_source_id_fkey', 'bot_source_associations', type_='foreignkey')
    op.create_foreign_key(
        'bot_source_associations_source_id_fkey',
        'bot_source_associations', 'sources',
        ['source_id'], ['source_id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Revert to original constraints without CASCADE
    op.drop_constraint('sources_owner_bot_id_fkey', 'sources', type_='foreignkey')
    op.create_foreign_key(
        'sources_owner_bot_id_fkey',
        'sources', 'bots',
        ['owner_bot_id'], ['bot_id']
    )
    
    op.drop_constraint('source_tools_source_id_fkey', 'source_tools', type_='foreignkey')
    op.create_foreign_key(
        'source_tools_source_id_fkey',
        'source_tools', 'sources',
        ['source_id'], ['source_id']
    )
    
    op.drop_constraint('bot_source_associations_bot_id_fkey', 'bot_source_associations', type_='foreignkey')
    op.create_foreign_key(
        'bot_source_associations_bot_id_fkey',
        'bot_source_associations', 'bots',
        ['bot_id'], ['bot_id']
    )
    
    op.drop_constraint('bot_source_associations_source_id_fkey', 'bot_source_associations', type_='foreignkey')
    op.create_foreign_key(
        'bot_source_associations_source_id_fkey',
        'bot_source_associations', 'sources',
        ['source_id'], ['source_id']
    ) 