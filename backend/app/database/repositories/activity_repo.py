from datetime import datetime, timezone
import json
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.models import UserActionLog


class ActivityRepository:
    @staticmethod
    async def log_action(
        db: AsyncSession,
        user_id: Optional[str],
        action_type: str,
        strategy_id: Optional[str] = None,
        symbol: Optional[str] = None,
        quantity: int = 0,
        price_paise: int = 0,
        message: str = "",
        details: Optional[dict[str, Any]] = None,
    ) -> UserActionLog:
        log_entry = UserActionLog(
            user_id=user_id,
            action_type=action_type,
            strategy_id=strategy_id,
            symbol=symbol,
            quantity=quantity,
            price_paise=price_paise,
            message=message,
            details_json=json.dumps(details or {}),
            timestamp=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        await db.flush()
        return log_entry

    @staticmethod
    async def get_user_activities(
        db: AsyncSession, user_id: Optional[str] = None, limit: int = 100
    ) -> list[UserActionLog]:
        stmt = select(UserActionLog)
        if user_id:
            stmt = stmt.where(UserActionLog.user_id == user_id)
        stmt = stmt.order_by(UserActionLog.timestamp.desc()).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())
