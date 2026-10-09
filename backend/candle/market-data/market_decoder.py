import getpass
import json
import os
import struct
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote

# Ensure current directory and backend root are on sys.path
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent.parent))

try:
    from websocket import WebSocketApp
except ImportError:
    WebSocketApp = None
from candle_aggregator import CandleAggregator

candle_1m = CandleAggregator(1)
candle_5m = CandleAggregator(5)

WS_BASE = "wss://devapi.021.trade/api/developer/websocket/market"

# 021 guide: exchange code 1 = NSE cash
EXCHANGE_CODE = 1
INSTRUMENT_TOKEN = 2885

# Guide's timestamp conversion: add this to seconds since 1980.
EPOCH_OFFSET = 315513000


def decode_full_nse_packet(packet: bytes) -> dict | None:
    """Decode one 220-byte TC 3 NSE cash packet."""
    if len(packet) < 220:
        return None

    transaction_code = struct.unpack_from(">H", packet, 0)[0]
    exchange = struct.unpack_from(">H", packet, 2)[0]

    if transaction_code != 3 or exchange != 1:
        return None

    token = struct.unpack_from(">I", packet, 4)[0]

    # Prices are unsigned 32-bit integers, expressed in paise.
    ltp = struct.unpack_from(">I", packet, 8)[0]
    last_trade_qty = struct.unpack_from(">I", packet, 12)[0]
    average_price = struct.unpack_from(">I", packet, 16)[0]

    # Volume is an unsigned 64-bit integer.
    volume = struct.unpack_from(">Q", packet, 20)[0]

    close_price = struct.unpack_from(">I", packet, 44)[0]
    open_price = struct.unpack_from(">I", packet, 48)[0]
    high_price = struct.unpack_from(">I", packet, 52)[0]
    low_price = struct.unpack_from(">I", packet, 56)[0]

    last_trade_time = struct.unpack_from(">I", packet, 60)[0]
    exchange_time = struct.unpack_from(">I", packet, 216)[0]

    def rupees(paise: int) -> float:
        return paise / 100.0

    def decode_time(seconds: int):
        if seconds == 0:
            return None
        return datetime.fromtimestamp(
            seconds + EPOCH_OFFSET, tz=timezone.utc
        ).isoformat()

    return {
        "exchange": exchange,
        "token": token,
        "ltp": rupees(ltp),
        "last_trade_qty": last_trade_qty,
        "average_price": rupees(average_price),
        "volume": volume,
        "open": rupees(open_price),
        "high": rupees(high_price),
        "low": rupees(low_price),
        "close": rupees(close_price),
        "last_trade_time": decode_time(last_trade_time),
        "exchange_time": decode_time(exchange_time),
    }


def process_binary_frame(data: bytes):
    """A frame may contain multiple packets back-to-back."""
    offset = 0

    while offset + 2 <= len(data):
        tc = struct.unpack_from(">H", data, offset)[0]

        # TC 10 is the documented two-byte heartbeat.
        if tc == 10:
            offset += 2
            continue

        if offset + 4 > len(data):
            print("Incomplete packet header")
            break

        exchange = struct.unpack_from(">H", data, offset + 2)[0]

        # Documented packet sizes for full mode.
        if tc == 1:
            packet_size = 12
        elif tc == 3 and exchange == 1:
            packet_size = 220
        elif tc == 3 and exchange == 2:
            packet_size = 234
        elif tc == 3 and exchange == 3:
            packet_size = 36
        elif tc == 3 and exchange in (4, 5, 6):
            packet_size = 262
        else:
            print(
                f"Unknown packet: TC={tc}, exchange={exchange}, "
                f"offset={offset}; stopping frame decode"
            )
            break

        if offset + packet_size > len(data):
            print(
                f"Incomplete packet: need {packet_size} bytes, "
                f"have {len(data) - offset}"
            )
            break

        packet = data[offset : offset + packet_size]
        decoded = None

        if tc == 3 and exchange == 1:
            decoded = decode_full_nse_packet(packet)

        if decoded:
            for candle in candle_1m.update(decoded):
                print("1-MIN CANDLE:", json.dumps(candle))

            for candle in candle_5m.update(decoded):
                print("5-MIN CANDLE:", json.dumps(candle))

        elif tc == 1:
            token = struct.unpack_from(">I", packet, 4)[0]
            ltp = struct.unpack_from(">i", packet, 8)[0]
            print(json.dumps({
                "transaction_code": 1,
                "exchange": exchange,
                "token": token,
                "ltp": ltp / 100.0,
            }))

        else:
            print(
                f"Recognized packet TC={tc}, exchange={exchange}; "
                "decoder for this exchange not implemented yet."
            )

        offset += packet_size


def on_open(ws):
    print("WebSocket connected. Subscribing...")
    ws.send(json.dumps({
        "Task": "subscribe",
        "Mode": "full",
        "Instruments": [[EXCHANGE_CODE, INSTRUMENT_TOKEN]],
    }))


def on_message(ws, message):
    if isinstance(message, bytes):
        process_binary_frame(message)
    else:
        print("Text message:", message)


def on_error(ws, error):
    print("WebSocket error:", error)


def on_close(ws, status_code, message):
    print("WebSocket closed:", status_code, message)


if __name__ == "__main__":
    token = os.environ.get("EPHEMERAL_TOKEN")
    if not token:
        # Check settings
        try:
            from app.core.config import get_settings
            from app.broker.api_021 import Broker021
            import asyncio
            b = Broker021()
            token = asyncio.run(b.get_valid_token())
        except Exception:
            token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJDTElFTlRcdTAwM2NcdTAwM2UzNDIiLCJleHAiOjE3OTE2MTY1NDQsImp0aSI6ImQ2ZmIxNTA2LWE0NGUtNDg2YS1iYmZlLTQ3M2NjYWY1ZDBkMCIsImlhdCI6MTc5MTUzMDE0NCwic3ViIjoiSEFDSzM0MiIsImNsdXN0ZXIiOiJudHQifQ.Lp_teVa4wyK6RQ2_treQteU5vSnChqCNS1OcQa9iooA"

    url = f"{WS_BASE}?token={quote(token, safe='')}"
    print(f"Connecting to {WS_BASE}...")
    app = WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    app.run_forever()