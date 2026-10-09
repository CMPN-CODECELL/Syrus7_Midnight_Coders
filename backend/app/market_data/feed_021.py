import asyncio
from datetime import datetime, timezone
import json
import struct
from typing import Callable, Optional, TYPE_CHECKING
import httpx
import websockets

if TYPE_CHECKING:
    from app.broker.api_021 import Broker021

from app.core.config import Settings, get_settings
from app.core.enums import EXCHANGE_WS_CODE, Exchange
from app.market_data.candle import Tick
from app.market_data.decoder import parse_binary_frame_packets
from app.market_data.instruments import InstrumentRegistry, get_instrument_registry


class MarketFeed021:
    """Live binary market data WebSocket client for 021 Developer API.

    Connects to wss://devapi.021.trade/api/developer/websocket/market?token=<key>
    Decodes binary frames:
      - TC 1: LTP snapshot (12+ bytes)
      - TC 3: Full NSE Cash packet (220 bytes) with OHLCV & exchange timestamps
      - TC 10: Heartbeat (2 bytes)
    """

    def __init__(
        self,
        broker: "Broker021",
        on_tick: Optional[Callable[[Tick], None]] = None,
        registry: Optional[InstrumentRegistry] = None,
        settings: Optional[Settings] = None,
        mode: str = "full",
    ) -> None:
        self.broker = broker
        self.on_tick = on_tick
        self.registry = registry or get_instrument_registry()
        self.settings = settings or get_settings()
        self.mode = mode  # "full" (TC 3) or "ltpo" (TC 1)

        # Build ws url: e.g. wss://devapi.021.trade/api/developer/websocket/market
        self.ws_base_url = "wss://devapi.021.trade/api/developer/websocket/market"

        self._running: bool = False
        self._subscribed_tokens: set[int] = set()
        self._task: Optional[asyncio.Task] = None
        self._latest_open_prices: dict[int, int] = {}

    def subscribe_symbols(self, symbols: list[str], exchange: Exchange = Exchange.NSE) -> None:
        """Add symbols to the subscription list."""
        for sym in symbols:
            inst = self.registry.find_by_symbol(sym, exchange)
            if inst:
                self._subscribed_tokens.add(inst.token)

    def subscribe_tokens(self, tokens: list[int]) -> None:
        """Add raw instrument tokens to subscription."""
        for tok in tokens:
            self._subscribed_tokens.add(tok)

    async def get_ephemeral_key(self) -> str:
        """Fetch a fresh 24h ephemeral token for websocket connection."""
        token = await self.broker.get_valid_token()
        url = f"{self.broker.base_url}/websocket/ephemeral-key"
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return data["data"]["token"]

    async def start(self) -> None:
        """Start listening to market feed in the background."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop listening to market feed."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        """Main connection and auto-reconnect loop."""
        backoff = 1.0
        while self._running:
            try:
                ephemeral_key = await self.get_ephemeral_key()
                url = f"{self.ws_base_url}?token={ephemeral_key}"

                async with websockets.connect(url, ping_interval=20, ping_timeout=30) as ws:
                    backoff = 1.0  # Reset backoff on successful connect

                    # Send subscription message
                    if self._subscribed_tokens:
                        sub_msg = {
                            "Task": "subscribe",
                            "Mode": self.mode,
                            "Instruments": [[1, tok] for tok in self._subscribed_tokens],
                        }
                        await ws.send(json.dumps(sub_msg))

                    while self._running:
                        msg = await ws.recv()
                        if isinstance(msg, bytes):
                            self._parse_binary_frame(msg)

            except asyncio.CancelledError:
                break
            except Exception:
                if not self._running:
                    break
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    def _parse_binary_frame(self, data: bytes) -> None:
        """Parse binary frame using the full packet decoder."""
        packets = parse_binary_frame_packets(data)

        for pkt in packets:
            tc = pkt.get("transaction_code")
            if tc == 10:
                continue

            token = pkt.get("token", 0)
            inst = self.registry.find_by_token(token)
            symbol = inst.symbol if inst else str(token)

            if tc == 3:  # Full packet with OHLCV & timestamps
                tick = Tick(
                    symbol=symbol,
                    token=token,
                    exchange=Exchange.NSE,
                    ltp_paise=pkt["ltp_paise"],
                    volume=pkt.get("volume", 0),
                    open_paise=pkt.get("open_paise", 0),
                    high_paise=pkt.get("high_paise", 0),
                    low_paise=pkt.get("low_paise", 0),
                    close_paise=pkt.get("close_paise", 0),
                    exchange_time=pkt.get("exchange_dt"),
                    timestamp=datetime.now(timezone.utc),
                )
            elif tc == 1:  # LTP mode packet
                open_price = self._latest_open_prices.get(token, 0)
                tick = Tick(
                    symbol=symbol,
                    token=token,
                    exchange=Exchange.NSE,
                    ltp_paise=pkt["ltp_paise"],
                    open_paise=open_price,
                    timestamp=datetime.now(timezone.utc),
                )
            else:
                continue

            if self.on_tick:
                try:
                    if asyncio.iscoroutinefunction(self.on_tick):
                        asyncio.create_task(self.on_tick(tick))
                    else:
                        res = self.on_tick(tick)
                        if asyncio.iscoroutine(res):
                            asyncio.create_task(res)
                except Exception:
                    pass
