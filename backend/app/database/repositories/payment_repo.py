from datetime import datetime, timezone
import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.models import PaymentTransaction


class PaymentRepository:
    @staticmethod
    async def create_transaction(
        db: AsyncSession,
        user_id: str,
        amount_paise: int,
        payment_method: str = "WALLET",
        transaction_type: str = "SUBSCRIPTION_PURCHASE",
        status: str = "SUCCESS",
        reference_id: Optional[str] = None,
        remarks: str = "",
        subscription_id: Optional[int] = None,
    ) -> PaymentTransaction:
        txn_id = f"txn_{uuid.uuid4().hex[:12]}"
        ref = reference_id or f"REF_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"

        txn = PaymentTransaction(
            id=txn_id,
            user_id=user_id,
            subscription_id=subscription_id,
            amount_paise=amount_paise,
            currency="INR",
            payment_method=payment_method,
            status=status,
            transaction_type=transaction_type,
            reference_id=ref,
            remarks=remarks,
            created_at=datetime.now(timezone.utc),
        )
        db.add(txn)
        await db.flush()
        return txn

    @staticmethod
    async def get_user_transactions(db: AsyncSession, user_id: str, limit: int = 50) -> list[PaymentTransaction]:
        result = await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id == user_id)
            .order_by(PaymentTransaction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_all_transactions(db: AsyncSession, limit: int = 100) -> list[PaymentTransaction]:
        result = await db.execute(
            select(PaymentTransaction)
            .order_by(PaymentTransaction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
