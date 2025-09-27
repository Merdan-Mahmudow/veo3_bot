from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
import logging
import uuid
from typing import List

from api.database import get_async_session
from api.models import User, Role, AuditLog
from .auth.routes import get_user_service # Re-use the dependency
from api.crud.user import UserService

router = APIRouter(prefix="/admin", tags=["Admin Panel"])

# --- Schemas ---

class UserOut(BaseModel):
    id: uuid.UUID
    chat_id: str
    nickname: str
    roles: List[str]

class RoleUpdate(BaseModel):
    role_name: str
    action: str # "add" or "remove"

# --- Helper Functions ---

async def get_admin_user(user_service: UserService, session: AsyncSession) -> User:
    """Dependency to ensure the acting user is an admin."""
    # In a real app, the user_id would come from a secure auth token.
    # Here, we'll have to rely on the bot checking the role before calling.
    # This is a conceptual placeholder for proper auth.
    return True

# --- Endpoints ---

@router.get("/users", response_model=List[UserOut])
async def list_users(
    session: AsyncSession = Depends(get_async_session),
    # admin: bool = Depends(get_admin_user)
):
    """Lists all users for role management."""
    users_stmt = select(User).options(selectinload(User.roles)).order_by(User.nickname)
    result = await session.execute(users_stmt)
    users = result.scalars().all()

    return [UserOut(id=u.id, chat_id=u.chat_id, nickname=u.nickname, roles=[r.name for r in u.roles]) for u in users]

@router.post("/users/{user_id}/roles", status_code=200)
async def update_user_roles(
    user_id: uuid.UUID,
    role_update: RoleUpdate,
    session: AsyncSession = Depends(get_async_session),
    # admin_user: User = Depends(get_admin_user) # Placeholder for actor_id
):
    """Assigns or removes a role from a user."""
    user_stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role_name = role_update.role_name
    action = role_update.action

    # Find the role object
    role_stmt = select(Role).where(Role.name == role_name)
    role = (await session.execute(role_stmt)).scalar_one_or_none()
    if not role:
        # For simplicity, we can create roles on the fly if they don't exist
        role = Role(name=role_name)
        session.add(role)
        await session.flush()

    if action == "add":
        if role not in user.roles:
            user.roles.append(role)
    elif action == "remove":
        if role in user.roles:
            user.roles.remove(role)
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'add' or 'remove'.")

    # For now, assume a fixed admin ID for auditing until auth is implemented.
    # In a real app, this would come from the authenticated user dependency.
    admin_actor_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    audit_log = AuditLog(
        actor_id=admin_actor_id,
        action=f"role_{action}",
        entity="user",
        entity_id=user.id,
        payload_json={"role": role_name, "changed_by": "admin_placeholder"}
    )
    session.add(audit_log)

    await session.commit()
    return {"status": "ok", "roles": [r.name for r in user.roles]}