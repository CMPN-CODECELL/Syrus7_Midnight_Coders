from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import KillSwitchState, RiskLimit, Strategy

# (id, name, description, timeframe)
DEFAULT_STRATEGIES = [
    ("time_based", "Time-based entry and exit",
     "Enters at 9:15 IST and squares off at 15:15 IST.", None),
    ("breakout_1pct", "1% breakout from open",
     "Buys at open +1%, sells at open -1%; the platform manages a 5% target and 5% stop-loss.", None),
    ("sma_crossover", "SMA crossover (own strategy)",
     "Placeholder for our own rule-based strategy using 5-minute candles. Rename when the rules are final.", "5m"),
]

# Defaults, in paise: 5000 rupees max daily loss, 100 shares, 10 orders per minute
DEFAULT_MAX_DAILY_LOSS_PAISE = 500_000
DEFAULT_MAX_POSITION_SIZE = 100
DEFAULT_MAX_ORDERS_PER_MINUTE = 10


async def seed_defaults(session: AsyncSession) -> None:
    for strategy_id, name, description, timeframe in DEFAULT_STRATEGIES:
        if await session.get(Strategy, strategy_id) is None:
            session.add(Strategy(id=strategy_id, name=name, description=description,
                                 timeframe=timeframe, status="STOPPED"))
    await session.flush()

    for strategy_id, *_ in DEFAULT_STRATEGIES:
        existing = await session.scalar(select(RiskLimit).where(RiskLimit.strategy_id == strategy_id))
        if existing is None:
            session.add(RiskLimit(
                strategy_id=strategy_id,
                max_daily_loss_paise=DEFAULT_MAX_DAILY_LOSS_PAISE,
                max_position_size=DEFAULT_MAX_POSITION_SIZE,
                max_orders_per_minute=DEFAULT_MAX_ORDERS_PER_MINUTE,
            ))

    if await session.get(KillSwitchState, 1) is None:
        session.add(KillSwitchState(id=1, active=False))

    await session.commit()