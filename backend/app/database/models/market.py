from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("exchange", "token", "timeframe", "start_time", name="uq_candle"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(10))
    token: Mapped[int] = mapped_column(Integer)
    timeframe: Mapped[str] = mapped_column(String(5))                # "1m" / "5m"
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open_paise: Mapped[int] = mapped_column(BigInteger)
    high_paise: Mapped[int] = mapped_column(BigInteger)
    low_paise: Mapped[int] = mapped_column(BigInteger)
    close_paise: Mapped[int] = mapped_column(BigInteger)
    volume: Mapped[int] = mapped_column(BigInteger, default=0)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)