import asyncio
import sys
from pathlib import Path

# Ensure backend folder is in Python path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.broker.api_021 import Broker021
from app.market_data.feed_021 import MarketFeed021
from app.core.config import get_settings


async def main():
    settings = get_settings()
    print("=" * 60)
    print(" 021 REAL-TIME MARKET FEED VALIDATION SCRIPT ")
    print("=" * 60)
    print(f"UCC: {settings.api_ucc}")
    print(f"Broker Base URL: {settings.broker_base_url}")
    print("Connecting to 021 Market WebSocket...")

    broker = Broker021(settings=settings)

    tick_count = 0

    def on_tick_received(tick):
        nonlocal tick_count
        tick_count += 1
        print(
            f"[TICK #{tick_count}] Symbol: {tick.symbol:<10} "
            f"LTP: Rs.{tick.ltp_paise / 100:.2f} | Vol: {tick.volume} | "
            f"Time: {tick.timestamp.strftime('%H:%M:%S.%f')[:-3]}"
        )

    feed = MarketFeed021(broker=broker, on_tick=on_tick_received)
    feed.subscribe_symbols(["RELIANCE", "TCS", "INFY", "HDFCBANK"])

    try:
        await feed.start()
        print("[+] WebSocket feed task launched. Listening for live ticks (10 seconds)...\n")
        await asyncio.sleep(10)
    except Exception as e:
        print(f"[-] Error in feed execution: {e}")
    finally:
        await feed.stop()
        await broker.close()
        print("\n" + "=" * 60)
        print(f" VALIDATION COMPLETE - Total Realtime Ticks Received: {tick_count}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
