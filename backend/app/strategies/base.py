from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
import uuid

from app.broker.models import BrokerOrder, TradeFill
from app.core.enums import Side, StrategyStatus
from app.market_data.candle import Candle, Tick
from app.strategies.intents import OrderIntent


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies.

    Manages per-strategy position tracking, P&L isolation (L4),
    and event handling for ticks, candles, and order fills.
    """

    def __init__(
        self,
        strategy_id: str | None = None,
        name: str = "BaseStrategy",
        symbols: list[str] | None = None,
    ) -> None:
        self.strategy_id: str = strategy_id or f"strat_{uuid.uuid4().hex[:8]}"
        self.name: str = name
        self.symbols: list[str] = [s.upper() for s in (symbols or [])]
        self.status: StrategyStatus = StrategyStatus.STOPPED

        # Per-strategy isolated position state (L4)
        # Key: symbol -> net_quantity, buy_qty, sell_qty, buy_amt, sell_amt
        self.positions: dict[str, dict[str, int]] = {}
        self.realized_pnl_paise: int = 0
        self.unrealized_pnl_paise: int = 0
        self.total_charges_paise: int = 0
        self.fills: list[TradeFill] = []
        self.orders: dict[str, BrokerOrder] = {}

        # Last known LTP per symbol
        self.last_ltp_paise: dict[str, int] = {}

        # Signal history for strategy observability and user transparency
        self.signals: list[dict[str, Any]] = []

    def log_signal(self, side: Side, price_paise: int, note: str) -> None:
        """Record an algorithmic or manual signal for display to the user."""
        self.signals.insert(0, {
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "type": side.value,
            "price": round(price_paise / 100, 2),
            "note": note,
        })
        if len(self.signals) > 50:
            self.signals = self.signals[:50]

    def reset_state(self) -> None:
        """Reset intraday execution cycle flags so user can trade again without restarting."""
        pass

    def get_parameters(self) -> dict[str, Any]:
        """Return strategy parameters dictionary for customization."""
        return {
            "symbols": self.symbols,
        }

    def update_parameters(self, params: dict[str, Any]) -> None:
        """Dynamically update strategy parameters at runtime."""
        if "symbols" in params and isinstance(params["symbols"], list):
            self.symbols = [s.upper() for s in params["symbols"]]
        elif "symbol" in params and isinstance(params["symbol"], str) and params["symbol"].strip():
            self.symbols = [params["symbol"].strip().upper()]

    def square_off_intent(self, ltp_paise: int | None = None) -> list[OrderIntent]:
        """Generate market order intents to flatten open positions for this strategy."""
        from app.core.enums import Book, Exchange, Product, Validity
        intents: list[OrderIntent] = []
        for sym, pos in self.positions.items():
            net_qty = pos.get("net_qty", 0)
            if net_qty != 0:
                side = Side.SELL if net_qty > 0 else Side.BUY
                px = ltp_paise or self.last_ltp_paise.get(sym, 0)
                intents.append(
                    OrderIntent(
                        strategy_id=self.strategy_id,
                        symbol=sym,
                        exchange=Exchange.NSE,
                        side=side,
                        quantity=abs(net_qty),
                        price_paise=px,
                        product=Product.INTRADAY,
                        book=Book.RL,
                        validity=Validity.DAY,
                        tag=f"manual_square_off_{self.strategy_id}",
                    )
                )
        return intents

    def get_position(self, symbol: str) -> int:
        """Returns current net quantity held by this strategy for a symbol."""
        pos = self.positions.get(symbol.upper())
        return pos["net_qty"] if pos else 0

    def get_average_price(self, symbol: str) -> int:
        """Returns average entry price in paise for open position."""
        pos = self.positions.get(symbol.upper())
        if not pos or pos.get("net_qty", 0) == 0:
            return 0
        net_qty = pos.get("net_qty", 0)
        buy_qty = pos.get("buy_qty", 0)
        sell_qty = pos.get("sell_qty", 0)
        buy_amt = pos.get("buy_amt", pos.get("buy_val_paise", 0))
        sell_amt = pos.get("sell_amt", pos.get("sell_val_paise", 0))

        if net_qty > 0 and buy_qty > 0:
            return buy_amt // buy_qty
        if net_qty < 0 and sell_qty > 0:
            return sell_amt // sell_qty
        return 0

    def start(self) -> None:
        """Activate the strategy."""
        self.status = StrategyStatus.RUNNING

    def stop(self) -> None:
        """Gracefully stop the strategy."""
        self.status = StrategyStatus.STOPPED

    def halt(self) -> None:
        """Halt immediately (e.g. triggered by risk manager or kill switch)."""
        self.status = StrategyStatus.HALTED

    def on_fill(self, fill: TradeFill) -> None:
        """Update strategy-level isolated position and P&L on trade execution."""
        sym = fill.symbol.upper()
        if sym not in self.positions:
            self.positions[sym] = {
                "net_qty": 0,
                "buy_qty": 0,
                "sell_qty": 0,
                "buy_amt": 0,
                "sell_amt": 0,
            }

        pos = self.positions[sym]
        notional = fill.quantity * fill.price_paise
        self.fills.append(fill)
        self.total_charges_paise += (fill.brokerage_paise + fill.fee_paise)

        if fill.side == Side.BUY:
            pos["buy_qty"] += fill.quantity
            pos["buy_amt"] += notional
            pos["net_qty"] += fill.quantity
        else:
            pos["sell_qty"] += fill.quantity
            pos["sell_amt"] += notional
            pos["net_qty"] -= fill.quantity

        # Compute realized P&L on closed quantity
        closed_qty = min(pos["buy_qty"], pos["sell_qty"])
        if closed_qty > 0:
            avg_buy = pos["buy_amt"] // pos["buy_qty"] if pos["buy_qty"] else 0
            avg_sell = pos["sell_amt"] // pos["sell_qty"] if pos["sell_qty"] else 0
            self.realized_pnl_paise = closed_qty * (avg_sell - avg_buy)

        self._recalculate_unrealized_pnl(sym)

    def _recalculate_unrealized_pnl(self, symbol: str) -> None:
        """Recalculate open unrealized P&L based on last known LTP."""
        sym = symbol.upper()
        pos = self.positions.get(sym)
        if not pos or pos["net_qty"] == 0:
            self.unrealized_pnl_paise = 0
            return

        ltp = self.last_ltp_paise.get(sym)
        if not ltp:
            return

        avg_price = self.get_average_price(sym)
        net_qty = pos["net_qty"]
        # Unrealized P&L = (LTP - AvgPrice) * NetQty
        self.unrealized_pnl_paise = (ltp - avg_price) * net_qty

    def update_ltp(self, symbol: str, ltp_paise: int) -> None:
        """Update last traded price and unrealized P&L."""
        self.last_ltp_paise[symbol.upper()] = ltp_paise
        self._recalculate_unrealized_pnl(symbol)

    @property
    def net_pnl_paise(self) -> int:
        """Net P&L after brokerage and statutory fees in paise."""
        return (self.realized_pnl_paise + self.unrealized_pnl_paise) - self.total_charges_paise

    @abstractmethod
    def on_tick(self, tick: Tick) -> list[OrderIntent]:
        """Process incoming market tick and return order intents if any."""
        pass

    @abstractmethod
    def on_candle(self, candle: Candle) -> list[OrderIntent]:
        """Process completed candle and return order intents if any."""
        pass
