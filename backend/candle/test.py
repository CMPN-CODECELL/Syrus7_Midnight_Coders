import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Add market-data to path
market_data_dir = Path(__file__).resolve().parent / "market-data"
sys.path.insert(0, str(market_data_dir))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from candle_aggregator import CandleAggregator
from market_decoder import decode_full_nse_packet, process_binary_frame


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


def test_decoder():
    packet = build_mock_nse_full_packet()
    res = decode_full_nse_packet(packet)
    assert res is not None, "Failed to decode packet"
    assert res["token"] == 2885
    assert res["ltp"] == 2500.0
    assert res["volume"] == 150000
    assert res["open"] == 2490.0
    assert res["high"] == 2510.0
    assert res["low"] == 2480.0
    assert res["close"] == 2495.0
    assert res["exchange_time"] is not None
    print("[PASS] test_decoder: Successfully decoded 220-byte TC 3 NSE packet.")


def test_candle_aggregator():
    agg = CandleAggregator(1)
    try:
        from zoneinfo import ZoneInfo
        ist = ZoneInfo("Asia/Kolkata")
    except Exception:
        from datetime import timedelta
        ist = timezone(timedelta(hours=5, minutes=30))

    t1 = datetime(2026, 10, 9, 9, 15, 10, tzinfo=ist)
    t2 = datetime(2026, 10, 9, 9, 15, 45, tzinfo=ist)
    t3 = datetime(2026, 10, 9, 9, 16, 5, tzinfo=ist)  # Next 1m candle bucket

    tick1 = {"token": 2885, "ltp": 2500.0, "volume": 1000, "exchange_time": t1.isoformat()}
    tick2 = {"token": 2885, "ltp": 2515.0, "volume": 1250, "exchange_time": t2.isoformat()}
    tick3 = {"token": 2885, "ltp": 2495.0, "volume": 1500, "exchange_time": t3.isoformat()}

    assert agg.update(tick1) == []
    assert agg.update(tick2) == []
    closed = agg.update(tick3)

    assert len(closed) == 1, f"Expected 1 closed candle, got {len(closed)}"
    c = closed[0]
    assert c["token"] == 2885
    assert c["open"] == 2500.0
    assert c["high"] == 2515.0
    assert c["low"] == 2500.0
    assert c["close"] == 2515.0
    assert c["volume"] == 1250  # 1000 initial + 250 delta
    print("[PASS] test_candle_aggregator: Successfully aggregated OHLCV candle.")


def test_multi_packet_frame():
    # TC 10 Heartbeat (2 bytes)
    heartbeat = struct.pack(">H", 10)

    # TC 1 LTP (12 bytes)
    tc1 = struct.pack(">HHIi", 1, 1, 2885, 250000)

    # TC 3 Full (220 bytes)
    tc3 = build_mock_nse_full_packet()

    frame = heartbeat + tc1 + tc3
    process_binary_frame(frame)
    print("[PASS] test_multi_packet_frame: Successfully parsed mixed binary stream.")


if __name__ == "__main__":
    test_decoder()
    test_candle_aggregator()
    test_multi_packet_frame()
    print("\nAll candle tests passed successfully!")
