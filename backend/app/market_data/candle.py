from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Optional, Union
from pydantic import BaseModel, Field

from app.core.enums import Exchange, Timeframe

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))
EPOCH_OFFSET = 315513000


class Tick(BaseModel):
    """Raw tick data received from market websocket or simulator."""

    symbol: str
    token: int = 0
    exchange: Exchange = Exchange.NSE
    ltp_paise: int
    volume: int = 0
    open_paise: int = 0
    high_paise: int = 0
    low_paise: int = 0
    close_paise: int = 0
    exchange_time: Optional[datetime] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def ltp(self) -> float:
        return self.ltp_paise / 100.0


class Candle(BaseModel):
    """OHLCV candlestick generated over a timeframe (1m, 5m)."""

    symbol: str
    timeframe: Timeframe
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int = 0
    start_time: datetime
    is_closed: bool = False

    @property
    def open(self) -> float:
        return self.open_paise / 100.0

    @property
    def high(self) -> float:
        return self.high_paise / 100.0

    @property
    def low(self) -> float:
        return self.low_paise / 100.0

    @property
    def close(self) -> float:
        return self.close_paise / 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe.value if hasattr(self.timeframe, "value") else str(self.timeframe),
            "timestamp": self.start_time.isoformat(),
            "time": self.start_time.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "is_closed": self.is_closed,
        }


class CandleAggregator:
    """Aggregates raw market ticks into 1-minute and 5-minute OHLCV candles with IST alignment.

    Supports both:
      - Model-based ticks (app.market_data.Tick)
      - Raw dictionary ticks from 021 binary feed or market_decoder
    """

    def __init__(
        self,
        timeframe: Union[Timeframe, int] = Timeframe.M1,
        on_candle_closed: Optional[Callable[[Candle], None]] = None,
    ) -> None:
        if isinstance(timeframe, int):
            if timeframe == 1:
                self.timeframe = Timeframe.M1
            elif timeframe == 5:
                self.timeframe = Timeframe.M5
            else:
                raise ValueError("Supported timeframes: 1 and 5 minutes")
            self.timeframe_minutes = timeframe
        else:
            self.timeframe = timeframe
            self.timeframe_minutes = 1 if timeframe == Timeframe.M1 else 5

        self.seconds_per_candle = self.timeframe_minutes * 60
        self.on_candle_closed = on_candle_closed

        # Current in-progress candle per symbol / token
        self._current_candles: dict[str, Candle] = {}
        # Historical closed candles per symbol
        self._history: dict[str, list[Candle]] = {}
        # Cumulative volume tracker for delta computation
        self._last_cumulative_volume: dict[str, int] = {}

    def _bucket_start(self, dt: datetime, timeframe_minutes: Optional[int] = None) -> datetime:
        """Bucket timestamp to the candle boundary in IST (Asia/Kolkata)."""
        tf = timeframe_minutes or self.timeframe_minutes
        dt_ist = dt.astimezone(IST)
        minute = dt_ist.minute - (dt_ist.minute % tf)
        bucket_ist = dt_ist.replace(minute=minute, second=0, microsecond=0)
        return bucket_ist.astimezone(timezone.utc)

    def _get_candle_start(self, dt: datetime) -> datetime:
        return self._bucket_start(dt)

    def process_tick(self, tick_input: Union[Tick, dict[str, Any]]) -> Optional[Candle]:
        """Process incoming tick (Tick model or dict). Returns closed candle if boundary was crossed."""
        if isinstance(tick_input, dict):
            symbol = str(tick_input.get("symbol") or tick_input.get("token") or "UNKNOWN").upper()
            if "ltp_paise" in tick_input:
                ltp_paise = int(tick_input["ltp_paise"])
            elif "ltp" in tick_input:
                ltp_paise = int(round(float(tick_input["ltp"]) * 100))
            else:
                return None

            vol = int(tick_input.get("volume", 0))

            raw_time = tick_input.get("exchange_time") or tick_input.get("timestamp")
            if isinstance(raw_time, datetime):
                dt = raw_time
            elif isinstance(raw_time, str):
                try:
                    dt = datetime.fromisoformat(raw_time)
                except Exception:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            tick = Tick(
                symbol=symbol,
                token=int(tick_input.get("token", 0)),
                ltp_paise=ltp_paise,
                volume=vol,
                timestamp=dt,
            )
        else:
            tick = tick_input

        if tick.ltp_paise <= 0:
            return None

        candle_start = self._bucket_start(tick.timestamp)
        symbol = tick.symbol.upper()
        current = self._current_candles.get(symbol)
        closed_candle: Optional[Candle] = None

        # Calculate volume contribution
        prev_cum = self._last_cumulative_volume.get(symbol)
        if prev_cum is not None and tick.volume >= prev_cum and tick.volume > 1000:
            # Full market feed where volume is cumulative day volume
            vol_delta = tick.volume - prev_cum
        else:
            # Incremental tick volume
            vol_delta = tick.volume
        self._last_cumulative_volume[symbol] = tick.volume

        if current is not None and candle_start > current.start_time:
            # Previous candle is closed
            current.is_closed = True
            closed_candle = current
            if symbol not in self._history:
                self._history[symbol] = []
            self._history[symbol].append(current)

            if self.on_candle_closed:
                self.on_candle_closed(current)

            # Reset current
            current = None

        if current is None:
            # Initialize new candle
            current = Candle(
                symbol=symbol,
                timeframe=self.timeframe,
                open_paise=tick.ltp_paise,
                high_paise=tick.ltp_paise,
                low_paise=tick.ltp_paise,
                close_paise=tick.ltp_paise,
                volume=vol_delta,
                start_time=candle_start,
                is_closed=False,
            )
            self._current_candles[symbol] = current
        else:
            # Update running candle
            current.high_paise = max(current.high_paise, tick.ltp_paise)
            current.low_paise = min(current.low_paise, tick.ltp_paise)
            current.close_paise = tick.ltp_paise
            current.volume += vol_delta

        return closed_candle

    def update(self, tick: dict[str, Any]) -> list[dict[str, Any]]:
        """Compatible with standalone candle folder market_decoder interface.
        Returns a list of completed candles as dicts.
        """
        closed = self.process_tick(tick)
        if closed:
            return [{
                "token": tick.get("token", closed.symbol),
                "symbol": closed.symbol,
                "time": closed.start_time.astimezone(IST).isoformat(),
                "timeframe_minutes": self.timeframe_minutes,
                "open": closed.open,
                "high": closed.high,
                "low": closed.low,
                "close": closed.close,
                "volume": closed.volume,
            }]
        return []

    def get_history(self, symbol: str) -> list[Candle]:
        """Get list of closed candles for a symbol."""
        return self._history.get(symbol.upper(), [])

    def get_current(self, symbol: str) -> Optional[Candle]:
        """Get the current in-flight candle for a symbol."""
        return self._current_candles.get(symbol.upper())

    def get_all_candles(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        """Return combined closed and active candles in JSON dict format for charts."""
        sym = symbol.upper()
        candles = [c.to_dict() for c in self._history.get(sym, [])]
        curr = self._current_candles.get(sym)
        if curr:
            candles.append(curr.to_dict())
        return candles[-limit:]
