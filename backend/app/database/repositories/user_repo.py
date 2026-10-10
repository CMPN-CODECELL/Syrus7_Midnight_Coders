from datetime import datetime, timezone
import uuid
from typing import Any, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database.models.models import User


class UserRepository:
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        normalized_email = email.strip().lower()
        result = await db.execute(select(User).where(User.email == normalized_email))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(
        db: AsyncSession,
        name: str,
        email: str,
        password: str,
        role: str = "user",
        api_ucc: str = "HACK342",
        account_balance_paise: int = 10000000,
        subscription_tier: str = "FREE",
    ) -> User:
        user_id = f"u_{uuid.uuid4().hex[:12]}"
        pwd_hash = hash_password(password)
        user = User(
            id=user_id,
            name=name.strip(),
            email=email.strip().lower(),
            password_hash=pwd_hash,
            role=role,
            is_active=True,
            api_ucc=api_ucc or "HACK342",
            account_balance_paise=account_balance_paise,
            subscription_tier=subscription_tier,
            notifications_enabled=True,
            theme="light",
        )
        db.add(user)
        await db.flush()
        return user

    @staticmethod
    async def list_users(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        role: Optional[str] = None,
    ) -> tuple[list[User], int]:
        stmt = select(User)
        count_stmt = select(func.count(User.id))

        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(User.name.ilike(pattern) | User.email.ilike(pattern))
            count_stmt = count_stmt.where(User.name.ilike(pattern) | User.email.ilike(pattern))

        if role:
            stmt = stmt.where(User.role == role)
            count_stmt = count_stmt.where(User.role == role)

        total_res = await db.execute(count_stmt)
        total = total_res.scalar_one() or 0

        stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)
        users_res = await db.execute(stmt)
        users = list(users_res.scalars().all())

        return users, total

    @staticmethod
    async def update_user(db: AsyncSession, user: User, updates: dict[str, Any]) -> User:
        for key, value in updates.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)
        user.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return user

    @staticmethod
    async def update_balance(db: AsyncSession, user: User, delta_paise: int) -> int:
        new_balance = max(0, user.account_balance_paise + delta_paise)
        user.account_balance_paise = new_balance
        await db.flush()
        return new_balance

    @staticmethod
    async def deactivate_user(db: AsyncSession, user: User) -> User:
        user.is_active = False
        await db.flush()
        return user
