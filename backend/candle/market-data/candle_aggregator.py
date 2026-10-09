from datetime import datetime, timezone, timedelta
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))
EPOCH_OFFSET = 315513000


class CandleAggregator:
    def __init__(self, timeframe_minutes: int):
        if timeframe_minutes not in (1, 5):
            raise ValueError("Supported timeframes: 1 and 5 minutes")

        self.timeframe_minutes = timeframe_minutes
        self.current_candles: dict[tuple[Any, int], dict[str, Any]] = {}
        self.last_volume: dict[Any, int] = {}

    def _bucket_start(self, timestamp: datetime, timeframe: Optional[int] = None) -> datetime:
        tf = timeframe or self.timeframe_minutes
        timestamp = timestamp.astimezone(IST)
        minute = timestamp.minute - (timestamp.minute % tf)
        return timestamp.replace(minute=minute, second=0, microsecond=0)

    def update(self, tick: dict[str, Any]) -> list[dict[str, Any]]:
        token = tick.get("token") or tick.get("symbol")
        price = tick.get("ltp")
        if price is None and "ltp_paise" in tick:
            price = tick["ltp_paise"] / 100.0

        if price is None or price <= 0:
            return []

        # The API guide says exchange timestamps use seconds since
        # 1980-01-01; add its documented offset to get Unix seconds.
        raw_time = tick.get("exchange_time") or tick.get("timestamp")

        if isinstance(raw_time, datetime):
            timestamp = raw_time
        elif isinstance(raw_time, str):
            try:
                timestamp = datetime.fromisoformat(raw_time)
            except Exception:
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        timestamp = timestamp.astimezone(IST)
        completed = []

        cumulative_volume = tick.get("volume")
        previous_volume = self.last_volume.get(token)

        volume_delta = 0
        if cumulative_volume is not None:
            if previous_volume is not None:
                volume_delta = max(0, cumulative_volume - previous_volume)
            else:
                volume_delta = cumulative_volume
            self.last_volume[token] = cumulative_volume

        timeframe = self.timeframe_minutes
        bucket = self._bucket_start(timestamp, timeframe)
        key = (token, timeframe)
        current = self.current_candles.get(key)

        if current is not None and current["time"] != bucket:
            # Finalize the previous candle.
            completed.append({
                **current,
                "time": current["time"].isoformat(),
                "timeframe_minutes": timeframe,
                "volume": current["volume"],
            })
            current = None

        if current is None:
            current = {
                "token": token,
                "time": bucket,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 0,
            }
            self.current_candles[key] = current

        current["high"] = max(current["high"], price)
        current["low"] = min(current["low"], price)
        current["close"] = price
        current["volume"] += volume_delta

        return completed