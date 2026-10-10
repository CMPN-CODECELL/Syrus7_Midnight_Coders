import json
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.models import StrategyRecord


class StrategyRepository:
    @staticmethod
    async def get_by_id(db: AsyncSession, strategy_id: str) -> Optional[StrategyRecord]:
        result = await db.execute(select(StrategyRecord).where(StrategyRecord.id == strategy_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db: AsyncSession) -> list[StrategyRecord]:
        result = await db.execute(select(StrategyRecord).order_by(StrategyRecord.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def upsert_strategy(
        db: AsyncSession,
        strategy_id: str,
        name: str,
        symbol: str,
        description: str = "",
        timeframe: str = "1m",
        status: str = "RUNNING",
        strategy_type: str = "TimeBased",
        parameters: Optional[dict[str, Any]] = None,
        creator_id: Optional[str] = None,
        price_paise: int = 0,
    ) -> StrategyRecord:
        record = await StrategyRepository.get_by_id(db, strategy_id)
        param_json = json.dumps(parameters or {})

        if not record:
            record = StrategyRecord(
                id=strategy_id,
                creator_id=creator_id,
                name=name,
                description=description,
                symbol=symbol,
                timeframe=timeframe,
                status=status,
                strategy_type=strategy_type,
                parameters_json=param_json,
                is_public=True,
                price_paise=price_paise,
            )
            db.add(record)
        else:
            record.name = name
            record.symbol = symbol
            record.description = description
            record.timeframe = timeframe
            record.status = status
            record.strategy_type = strategy_type
            record.parameters_json = param_json
            if price_paise > 0:
                record.price_paise = price_paise

        await db.flush()
        return record

    @staticmethod
    async def delete_strategy(db: AsyncSession, strategy_id: str) -> bool:
        record = await StrategyRepository.get_by_id(db, strategy_id)
        if record:
            await db.delete(record)
            await db.flush()
            return True
        return False
