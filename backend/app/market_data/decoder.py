import struct
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))

# 021 Exchange epoch offset: exchange timestamps use seconds since 1980-01-01 00:00:00 UTC.
# Unix timestamp of 1980-01-01 00:00:00 UTC is 315532800 (or documented offset 315513000).
EPOCH_OFFSET = 315513000

# Packet sizes by transaction code and exchange
# TC 1: 12 bytes (LTP)
# TC 3: Exchange 1 (NSE Cash) = 220 bytes
#       Exchange 2 = 234 bytes
#       Exchange 3 = 36 bytes
#       Exchange 4, 5, 6 = 262 bytes
# TC 10: 2 bytes (Heartbeat)
TC3_PACKET_SIZES = {
    1: 220,  # NSE Cash
    2: 234,  # NSE FO
    3: 36,   # Indices
    4: 262,  # Currency
    5: 262,  # Commodity
    6: 262,  # BSE
}


def decode_exchange_time(seconds: int) -> Optional[datetime]:
    """Convert exchange epoch timestamp (seconds since 1980) to timezone-aware UTC datetime."""
    if not seconds:
        return None
    try:
        return datetime.fromtimestamp(seconds + EPOCH_OFFSET, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def decode_full_nse_packet(packet: bytes) -> Optional[dict[str, Any]]:
    """Decode one 220-byte TC 3 NSE cash binary packet from 021 market feed.

    Packet Structure:
      - 0..2: Transaction Code (uint16, expected 3)
      - 2..4: Exchange Code (uint16, expected 1 for NSE cash)
      - 4..8: Instrument Token (uint32)
      - 8..12: LTP (uint32, in paise)
      - 12..16: Last Traded Quantity (uint32)
      - 16..20: Average Traded Price (uint32, in paise)
      - 20..28: Cumulative Volume (uint64)
      - 44..48: Close Price (uint32, in paise)
      - 48..52: Open Price (uint32, in paise)
      - 52..56: High Price (uint32, in paise)
      - 56..60: Low Price (uint32, in paise)
      - 60..64: Last Trade Time (uint32, seconds since 1980)
      - 216..220: Exchange Timestamp (uint32, seconds since 1980)
    """
    if len(packet) < 220:
        return None

    transaction_code = struct.unpack_from(">H", packet, 0)[0]
    exchange = struct.unpack_from(">H", packet, 2)[0]

    if transaction_code != 3 or exchange != 1:
        return None

    token = struct.unpack_from(">I", packet, 4)[0]
    ltp_paise = struct.unpack_from(">I", packet, 8)[0]
    last_trade_qty = struct.unpack_from(">I", packet, 12)[0]
    average_price_paise = struct.unpack_from(">I", packet, 16)[0]
    volume = struct.unpack_from(">Q", packet, 20)[0]

    close_paise = struct.unpack_from(">I", packet, 44)[0]
    open_paise = struct.unpack_from(">I", packet, 48)[0]
    high_paise = struct.unpack_from(">I", packet, 52)[0]
    low_paise = struct.unpack_from(">I", packet, 56)[0]

    last_trade_time_raw = struct.unpack_from(">I", packet, 60)[0]
    exchange_time_raw = struct.unpack_from(">I", packet, 216)[0]

    last_trade_dt = decode_exchange_time(last_trade_time_raw)
    exchange_dt = decode_exchange_time(exchange_time_raw)

    return {
        "transaction_code": transaction_code,
        "exchange": exchange,
        "token": token,
        "ltp_paise": ltp_paise,
        "ltp": ltp_paise / 100.0,
        "last_trade_qty": last_trade_qty,
        "average_price_paise": average_price_paise,
        "average_price": average_price_paise / 100.0,
        "volume": volume,
        "open_paise": open_paise,
        "open": open_paise / 100.0,
        "high_paise": high_paise,
        "high": high_paise / 100.0,
        "low_paise": low_paise,
        "low": low_paise / 100.0,
        "close_paise": close_paise,
        "close": close_paise / 100.0,
        "last_trade_time": last_trade_dt.isoformat() if last_trade_dt else None,
        "exchange_time": exchange_dt.isoformat() if exchange_dt else None,
        "exchange_dt": exchange_dt,
    }


def parse_binary_frame_packets(data: bytes) -> list[dict[str, Any]]:
    """Parse multiple packets inside a binary websocket frame.
    Supports TC 10 (Heartbeat), TC 1 (LTP), TC 3 (Full packets for various exchanges).
    """
    packets: list[dict[str, Any]] = []
    offset = 0
    total_len = len(data)

    while offset + 2 <= total_len:
        tc = struct.unpack_from(">H", data, offset)[0]

        # TC 10 is the 2-byte heartbeat
        if tc == 10:
            packets.append({"transaction_code": 10, "type": "heartbeat"})
            offset += 2
            continue

        if offset + 4 > total_len:
            break

        exchange = struct.unpack_from(">H", data, offset + 2)[0]

        # Determine packet size
        if tc == 1:
            packet_size = 12
        elif tc == 3:
            packet_size = TC3_PACKET_SIZES.get(exchange, 220)
        else:
            # Unknown packet code, safely stop
            break

        if offset + packet_size > total_len:
            break

        packet_bytes = data[offset : offset + packet_size]

        if tc == 3 and exchange == 1:
            decoded = decode_full_nse_packet(packet_bytes)
            if decoded:
                packets.append(decoded)
        elif tc == 1:
            token = struct.unpack_from(">I", packet_bytes, 4)[0]
            ltp = struct.unpack_from(">i", packet_bytes, 8)[0]
            packets.append({
                "transaction_code": 1,
                "exchange": exchange,
                "token": token,
                "ltp_paise": ltp,
                "ltp": ltp / 100.0,
            })
        else:
            packets.append({
                "transaction_code": tc,
                "exchange": exchange,
                "raw_bytes_len": len(packet_bytes),
            })

        offset += packet_size

    return packets
