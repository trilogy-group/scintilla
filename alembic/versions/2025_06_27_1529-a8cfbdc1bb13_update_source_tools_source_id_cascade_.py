"""update_source_tools_source_id_cascade_delete

Revision ID: a8cfbdc1bb13
Revises: 9dd32f3ad27b
Create Date: 2025-06-27 15:29:34.404405

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8cfbdc1bb13'
down_revision = '9dd32f3ad27b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing foreign key constraint
    op.drop_constraint('source_tools_source_id_fkey', 'source_tools', type_='foreignkey')
    
    # Recreate the foreign key constraint with CASCADE DELETE
    op.create_foreign_key(
        'source_tools_source_id_fkey',
        'source_tools', 'sources',
        ['source_id'], ['source_id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Drop the CASCADE foreign key constraint
    op.drop_constraint('source_tools_source_id_fkey', 'source_tools', type_='foreignkey')
    
    # Recreate the original foreign key constraint with NO ACTION
    op.create_foreign_key(
        'source_tools_source_id_fkey',
        'source_tools', 'sources',
        ['source_id'], ['source_id']
    ) 