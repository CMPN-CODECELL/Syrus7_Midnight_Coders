import struct
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest

from app.core.enums import Timeframe
from app.market_data import (
    Candle,
    CandleAggregator,
    Tick,
    decode_full_nse_packet,
    parse_binary_frame_packets,
)


def build_mock_nse_full_packet(
    token: int = 2885,
    ltp_paise: int = 250000,
    volume: int = 150000,
    open_paise: int = 249000,
    high_paise: int = 251000,
    low_paise: int = 248000,
    close_paise: int = 249500,
    exchange_seconds: int = 1160000000,
) -> bytes:
    """Build a 220-byte TC 3 NSE Cash binary packet for testing."""
    buf = bytearray(220)
    struct.pack_into(">H", buf, 0, 3)         # TC = 3
    struct.pack_into(">H", buf, 2, 1)         # Exchange = 1 (NSE)
    struct.pack_into(">I", buf, 4, token)     # Token
    struct.pack_into(">I", buf, 8, ltp_paise) # LTP
    struct.pack_into(">I", buf, 12, 100)      # Last trade qty
    struct.pack_into(">I", buf, 16, 249800)   # Average price
    struct.pack_into(">Q", buf, 20, volume)   # Cumulative volume
    struct.pack_into(">I", buf, 44, close_paise)
    struct.pack_into(">I", buf, 48, open_paise)
    struct.pack_into(">I", buf, 52, high_paise)
    struct.pack_into(">I", buf, 56, low_paise)
    struct.pack_into(">I", buf, 60, exchange_seconds - 5)  # Last trade time
    struct.pack_into(">I", buf, 216, exchange_seconds)     # Exchange time
    return bytes(buf)


def test_decode_full_nse_packet():
    packet = build_mock_nse_full_packet()
    res = decode_full_nse_packet(packet)
    assert res is not None
    assert res["transaction_code"] == 3
    assert res["exchange"] == 1
    assert res["token"] == 2885
    assert res["ltp"] == 2500.0
    assert res["volume"] == 150000
    assert res["open"] == 2490.0
    assert res["high"] == 2510.0
    assert res["low"] == 2480.0
    assert res["close"] == 2495.0
    assert res["exchange_time"] is not None


def test_parse_binary_frame_stream():
    heartbeat = struct.pack(">H", 10)
    tc1 = struct.pack(">HHIi", 1, 1, 2885, 250000)
    tc3 = build_mock_nse_full_packet(token=2885, ltp_paise=251000)

    frame = heartbeat + tc1 + tc3
    packets = parse_binary_frame_packets(frame)

    assert len(packets) == 3
    assert packets[0]["transaction_code"] == 10
    assert packets[1]["transaction_code"] == 1
    assert packets[1]["ltp_paise"] == 250000
    assert packets[2]["transaction_code"] == 3
    assert packets[2]["ltp_paise"] == 251000


def test_candle_aggregator_dict_and_model_interop():
    agg = CandleAggregator(Timeframe.M1)
    try:
        from zoneinfo import ZoneInfo
        ist = ZoneInfo("Asia/Kolkata")
    except Exception:
        from datetime import timedelta
        ist = timezone(timedelta(hours=5, minutes=30))

    t1 = datetime(2026, 10, 9, 9, 15, 10, tzinfo=ist)
    t2 = datetime(2026, 10, 9, 9, 15, 45, tzinfo=ist)
    t3 = datetime(2026, 10, 9, 9, 16, 5, tzinfo=ist)

    # Dictionary input
    agg.process_tick({"token": 2885, "symbol": "RELIANCE", "ltp": 2500.0, "volume": 100, "exchange_time": t1.isoformat()})
    # Model input
    agg.process_tick(Tick(symbol="RELIANCE", token=2885, ltp_paise=251500, volume=150, timestamp=t2))
    # Boundary cross
    closed = agg.process_tick({"symbol": "RELIANCE", "ltp": 2495.0, "volume": 200, "exchange_time": t3.isoformat()})

    assert closed is not None
    assert closed.symbol == "RELIANCE"
    assert closed.open_paise == 250000
    assert closed.high_paise == 251500
    assert closed.low_paise == 250000
    assert closed.close_paise == 251500
    assert closed.volume == 250
    assert closed.is_closed is True


def test_empty_minute_gap_handling():
    closed_candles = []
    agg = CandleAggregator(Timeframe.M1, on_candle_closed=lambda c: closed_candles.append(c))

    try:
        from zoneinfo import ZoneInfo
        ist = ZoneInfo("Asia/Kolkata")
    except Exception:
        from datetime import timedelta
        ist = timezone(timedelta(hours=5, minutes=30))

    t1 = datetime(2026, 10, 9, 9, 15, 10, tzinfo=ist)
    t2 = datetime(2026, 10, 9, 9, 18, 15, tzinfo=ist)  # 3 minutes gap (16:00 and 17:00 empty)

    agg.process_tick({"symbol": "INFY", "ltp": 1500.0, "volume": 1000, "exchange_time": t1.isoformat()})
    agg.process_tick({"symbol": "INFY", "ltp": 1510.0, "volume": 500, "exchange_time": t2.isoformat()})

    # Total closed candles should be 3: 09:15 (real), 09:16 (empty gap), 09:17 (empty gap)
    history = agg.get_history("INFY")
    assert len(history) == 3
    assert len(closed_candles) == 3

    # Check 09:15 real candle
    assert history[0].close_paise == 150000
    assert history[0].volume == 1000

    # Check 09:16 carry-forward candle
    assert history[1].open_paise == 150000
    assert history[1].high_paise == 150000
    assert history[1].low_paise == 150000
    assert history[1].close_paise == 150000
    assert history[1].volume == 0

    # Check 09:17 carry-forward candle
    assert history[2].open_paise == 150000
    assert history[2].close_paise == 150000
    assert history[2].volume == 0


def test_strategy_entry_condition_uses_candles():
    from app.strategies.moving_average import MovingAverageCrossStrategy
    from app.core.enums import StrategyStatus, Side

    strategy = MovingAverageCrossStrategy(
        strategy_id="strat-ma-1",
        symbol="TCS",
        timeframe=Timeframe.M1,
        fast_period=2,
        slow_period=3,
    )
    strategy.start()

    # Feed closed candles to strategy to cause a golden crossover
    c1 = Candle(symbol="TCS", timeframe=Timeframe.M1, open_paise=1000, high_paise=1000, low_paise=1000, close_paise=1000, volume=10, start_time=datetime.now(timezone.utc), is_closed=True)
    c2 = Candle(symbol="TCS", timeframe=Timeframe.M1, open_paise=950, high_paise=950, low_paise=950, close_paise=950, volume=10, start_time=datetime.now(timezone.utc), is_closed=True)
    c3 = Candle(symbol="TCS", timeframe=Timeframe.M1, open_paise=900, high_paise=900, low_paise=900, close_paise=900, volume=10, start_time=datetime.now(timezone.utc), is_closed=True)
    c4 = Candle(symbol="TCS", timeframe=Timeframe.M1, open_paise=1200, high_paise=1200, low_paise=1200, close_paise=1200, volume=10, start_time=datetime.now(timezone.utc), is_closed=True)

    intents1 = strategy.on_candle(c1)
    intents2 = strategy.on_candle(c2)
    intents3 = strategy.on_candle(c3)
    # Slow SMA = (1000+950+900)/3 = 950, Fast SMA = (950+900)/2 = 925 (Fast <= Slow)

    intents4 = strategy.on_candle(c4)
    # Slow SMA = (950+900+1200)/3 = 1016.6, Fast SMA = (900+1200)/2 = 1050 (Fast > Slow -> Golden Cross)

    assert len(intents4) == 1
    intent = intents4[0]
    assert intent.side == Side.BUY
    assert intent.symbol == "TCS"
    assert intent.price_paise == 1200
    assert strategy.in_trade is True

