"""
Agent Token Management API Endpoints

Provides REST endpoints for users to create, list, and revoke
agent tokens for local agent authentication.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.models import (
    AgentTokenCreate, AgentTokenResponse, AgentTokenListResponse, DeleteResponse
)
from src.auth.google_oauth import get_current_user
from src.auth.agent_tokens import AgentTokenService
from src.db.base import get_db_session
from src.db.models import User
from uuid import UUID

router = APIRouter(prefix="/agent-tokens", tags=["agent-tokens"])


@router.post("/", response_model=AgentTokenResponse)
async def create_agent_token(
    request: AgentTokenCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new agent token for the authenticated user
    
    The token will be shown only once in the response. Store it securely.
    """
    try:
        token_record, plain_token = await AgentTokenService.create_token(
            db=db,
            user_id=user.user_id,
            name=request.name,
            expires_days=request.expires_days
        )
        
        # Extract ALL attributes before commit (prevents greenlet errors)
        token_id_value = token_record.token_id
        token_name_value = token_record.name
        token_prefix_value = token_record.token_prefix
        token_last_used_at = token_record.last_used_at
        token_expires_at = token_record.expires_at
        token_is_active = token_record.is_active
        token_created_at = token_record.created_at
        
        await db.commit()
        
        return AgentTokenResponse(
            token_id=token_id_value,
            name=token_name_value,
            token_prefix=token_prefix_value,
            token=plain_token,  # Only shown during creation
            last_used_at=token_last_used_at,
            expires_at=token_expires_at,
            is_active=token_is_active,
            created_at=token_created_at
        )
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create token: {str(e)}")


@router.get("/", response_model=AgentTokenListResponse)
async def list_agent_tokens(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List all active agent tokens for the authenticated user"""
    
    tokens = await AgentTokenService.list_user_tokens(db, user.user_id)
    
    return AgentTokenListResponse(
        tokens=[
            AgentTokenResponse(
                token_id=token.token_id,
                name=token.name,
                token_prefix=token.token_prefix,
                token=None,  # Never show full token in list
                last_used_at=token.last_used_at,
                expires_at=token.expires_at,
                is_active=token.is_active,
                created_at=token.created_at
            )
            for token in tokens
        ]
    )


@router.delete("/{token_id}", response_model=DeleteResponse)
async def revoke_agent_token(
    token_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Revoke (deactivate) a specific agent token"""
    
    success = await AgentTokenService.revoke_token(db, user.user_id, token_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    
    await db.commit()
    
    return DeleteResponse(message="Agent token revoked successfully")


@router.delete("/", response_model=DeleteResponse)
async def revoke_all_agent_tokens(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Revoke all agent tokens for the authenticated user"""
    
    revoked_count = await AgentTokenService.revoke_all_tokens(db, user.user_id)
    
    await db.commit()
    
    return DeleteResponse(message=f"Revoked {revoked_count} agent tokens") 