"""API dependencies for authentication and database access."""

from typing import Annotated, Optional, Sequence
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.supervisor_membership import SupervisorMembership, SupervisorRole
from supervisor.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: int = payload.get("user_id")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Verify that the current user is active."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# --- Supervisor-scoped authorization helpers ---

def get_user_supervisor_role(
    db: Session,
    user_id: int,
    supervisor_id: int,
) -> Optional[SupervisorRole]:
    """Get a user's role for a specific supervisor, or None if not a member."""
    membership = db.query(SupervisorMembership).filter(
        SupervisorMembership.user_id == user_id,
        SupervisorMembership.supervisor_id == supervisor_id,
    ).first()
    return membership.role if membership else None


def require_supervisor_role(
    db: Session,
    user: User,
    supervisor_id: int,
    allowed_roles: Sequence[SupervisorRole],
) -> SupervisorRole:
    """Verify user has one of the allowed roles for a supervisor.

    Args:
        db: Database session
        user: Current user
        supervisor_id: ID of the supervisor to check
        allowed_roles: List of roles that grant access

    Returns:
        The user's role if authorized

    Raises:
        HTTPException 403 if user lacks required role
    """
    role = get_user_supervisor_role(db, user.id, supervisor_id)
    if role is None or role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of roles: {[r.value for r in allowed_roles]} for this supervisor",
        )
    return role


def require_any_supervisor_role(
    db: Session,
    user: User,
    supervisor_id: int,
) -> SupervisorRole:
    """Verify user has any role for a supervisor (is a member).

    Args:
        db: Database session
        user: Current user
        supervisor_id: ID of the supervisor to check

    Returns:
        The user's role if a member

    Raises:
        HTTPException 403 if user is not a member
    """
    role = get_user_supervisor_role(db, user.id, supervisor_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this supervisor",
        )
    return role
