import struct
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest

from app.core.enums import Timeframe
from app.market_data import (
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
