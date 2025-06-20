"""add_direct_sse_and_bearer_token_support

Revision ID: 48c3c7adba19
Revises: e50222e547d6
Create Date: 2025-06-19 16:01:15.712611

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '48c3c7adba19'
down_revision = 'e50222e547d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new server types to MCPServerType enum
    op.execute("ALTER TYPE mcpservertype ADD VALUE 'DIRECT_SSE'")
    op.execute("ALTER TYPE mcpservertype ADD VALUE 'WEBSOCKET'")
    
    # Add new credential types to CredentialType enum
    op.execute("ALTER TYPE credentialtype ADD VALUE 'BEARER_TOKEN'")
    op.execute("ALTER TYPE credentialtype ADD VALUE 'CUSTOM_HEADERS'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # In production, you'd need to recreate the enum types if rollback is needed
    pass 