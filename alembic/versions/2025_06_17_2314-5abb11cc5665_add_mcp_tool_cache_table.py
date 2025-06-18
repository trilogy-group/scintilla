"""add_mcp_tool_cache_table

Revision ID: 5abb11cc5665
Revises: f682461ce5d1
Create Date: 2025-06-17 23:14:37.112071

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5abb11cc5665'
down_revision = 'f682461ce5d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the new table first
    op.create_table('mcp_tool_cache',
    sa.Column('cache_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('bot_source_ids', sa.ARRAY(sa.UUID()), nullable=True),
    sa.Column('tools_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('loaded_servers', sa.ARRAY(sa.String()), nullable=False),
    sa.Column('tool_count', sa.String(), nullable=False),
    sa.Column('cache_key', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_refreshed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('cache_id')
    )
    op.create_index(op.f('ix_mcp_tool_cache_cache_key'), 'mcp_tool_cache', ['cache_key'], unique=True)
    
    # Create enums first
    credentialtype_enum = postgresql.ENUM('API_KEY_HEADER', name='credentialtype')
    credentialtype_enum.create(op.get_bind())
    
    mcpservertype_enum = postgresql.ENUM('CUSTOM_SSE', name='mcpservertype')
    mcpservertype_enum.create(op.get_bind())
    
    # Convert columns with USING clause
    op.execute("ALTER TABLE mcp_credentials ALTER COLUMN credential_type TYPE credentialtype USING credential_type::credentialtype")
    op.execute("ALTER TABLE sources ALTER COLUMN server_type TYPE mcpservertype USING server_type::mcpservertype")


def downgrade() -> None:
    # Convert back to VARCHAR
    op.alter_column('sources', 'server_type',
               existing_type=sa.Enum('CUSTOM_SSE', name='mcpservertype'),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    op.alter_column('mcp_credentials', 'credential_type',
               existing_type=sa.Enum('API_KEY_HEADER', name='credentialtype'),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    
    # Drop enums
    op.execute("DROP TYPE credentialtype")
    op.execute("DROP TYPE mcpservertype")
    
    # Drop table
    op.drop_index(op.f('ix_mcp_tool_cache_cache_key'), table_name='mcp_tool_cache')
    op.drop_table('mcp_tool_cache') 