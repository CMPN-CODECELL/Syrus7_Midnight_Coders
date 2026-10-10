from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.models import OrderRecord, RiskEventRecord, TradeFillRecord


class OrderRepository:
    @staticmethod
    async def save_order(
        db: AsyncSession,
        order_id: str,
        client_order_id: str,
        strategy_id: str,
        symbol: str,
        side: str,
        quantity: int,
        price_paise: int = 0,
        filled_quantity: int = 0,
        exchange: str = "NSE",
        product: str = "INTRADAY",
        status: str = "CREATED",
        user_id: Optional[str] = None,
        rejection_reason: Optional[str] = None,
    ) -> OrderRecord:
        result = await db.execute(select(OrderRecord).where(OrderRecord.id == order_id))
        ord_rec = result.scalar_one_or_none()

        if not ord_rec:
            ord_rec = OrderRecord(
                id=order_id,
                client_order_id=client_order_id,
                user_id=user_id,
                strategy_id=strategy_id,
                symbol=symbol,
                exchange=exchange,
                side=side,
                quantity=quantity,
                filled_quantity=filled_quantity,
                price_paise=price_paise,
                product=product,
                status=status,
                rejection_reason=rejection_reason,
                created_at=datetime.now(timezone.utc),
            )
            db.add(ord_rec)
        else:
            ord_rec.filled_quantity = filled_quantity
            ord_rec.status = status
            if rejection_reason:
                ord_rec.rejection_reason = rejection_reason

        await db.flush()
        return ord_rec

    @staticmethod
    async def save_fill(
        db: AsyncSession,
        order_id: str,
        strategy_id: str,
        symbol: str,
        side: str,
        quantity: int,
        price_paise: int,
        user_id: Optional[str] = None,
        brokerage_paise: int = 2000,
        fee_paise: int = 150,
    ) -> TradeFillRecord:
        fill = TradeFillRecord(
            order_id=order_id,
            user_id=user_id,
            strategy_id=strategy_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price_paise=price_paise,
            brokerage_paise=brokerage_paise,
            fee_paise=fee_paise,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(fill)
        await db.flush()
        return fill

    @staticmethod
    async def save_risk_event(
        db: AsyncSession,
        strategy_id: str,
        symbol: str,
        side: str,
        quantity: int,
        passed: bool,
        price_paise: int = 0,
        reason: Optional[str] = None,
        message: str = "",
        severity: str = "INFO",
        user_id: Optional[str] = None,
    ) -> RiskEventRecord:
        rec = RiskEventRecord(
            user_id=user_id,
            strategy_id=strategy_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price_paise=price_paise,
            passed=passed,
            reason=reason,
            message=message,
            severity=severity,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(rec)
        await db.flush()
        return rec

    @staticmethod
    async def get_orders(
        db: AsyncSession,
        user_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[OrderRecord]:
        stmt = select(OrderRecord)
        if user_id:
            stmt = stmt.where(OrderRecord.user_id == user_id)
        if strategy_id:
            stmt = stmt.where(OrderRecord.strategy_id == strategy_id)
        stmt = stmt.order_by(OrderRecord.created_at.desc()).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_fills(
        db: AsyncSession,
        user_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[TradeFillRecord]:
        stmt = select(TradeFillRecord)
        if user_id:
            stmt = stmt.where(TradeFillRecord.user_id == user_id)
        if strategy_id:
            stmt = stmt.where(TradeFillRecord.strategy_id == strategy_id)
        stmt = stmt.order_by(TradeFillRecord.timestamp.desc()).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())
