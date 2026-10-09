from typing import Any
from app.broker.models import TradeFill
from app.core.enums import Book, Exchange, Product, Side, StrategyStatus, Validity
from app.market_data.candle import Candle, Tick
from app.strategies.base import BaseStrategy
from app.strategies.intents import OrderIntent


class BreakoutStrategy(BaseStrategy):
    """Strategy 2: Open breakout with customizable breakout %, target %, stop-loss %, and direction.

    Rules:
    1. Read open price (from tick or configured).
    2. On LTP update:
       - Upward breakout: LTP >= open * (1 + breakout_pct) -> BUY entry (if direction != SHORT_ONLY).
       - Downward breakout: LTP <= open * (1 - breakout_pct) -> SELL entry (if direction != LONG_ONLY).
    3. Once filled, manages dynamic target and stop-loss:
       - Optional trailing stop-loss as market price moves favorably.
    4. On target or stop-loss hit: closes position with an opposite order.
    5. Fully customizable by user at runtime (quantities, thresholds, directions, trailing SL).
    """

    def __init__(
        self,
        strategy_id: str | None = None,
        name: str = "BreakoutStrategy",
        symbol: str = "RELIANCE",
        exchange: Exchange = Exchange.NSE,
        quantity: int = 1,
        open_price_paise: int | None = None,
        tick_size_paise: int = 5,
        breakout_pct: float = 0.01,         # Default 1.0%
        target_pct: float = 0.05,           # Default 5.0%
        stop_loss_pct: float = 0.05,        # Default 5.0%
        direction: str = "BOTH",            # "BOTH", "LONG_ONLY", "SHORT_ONLY"
        trailing_stop_pct: float | None = None,
    ) -> None:
        super().__init__(strategy_id=strategy_id, name=name, symbols=[symbol])
        self.symbol = symbol.upper()
        self.exchange = exchange
        self.quantity = quantity
        self.open_price_paise = open_price_paise
        self.tick_size_paise = tick_size_paise
        self.breakout_pct = breakout_pct
        self.target_pct = target_pct
        self.stop_loss_pct = stop_loss_pct
        self.direction = direction.upper()
        self.trailing_stop_pct = trailing_stop_pct

        self.in_trade: bool = False
        self.entry_side: Side | None = None
        self.entry_price_paise: int = 0
        self.target_price_paise: int = 0
        self.stop_loss_price_paise: int = 0
        self.highest_price_paise: int = 0
        self.lowest_price_paise: int = 0
        self.trade_completed: bool = False

    def _round_to_tick(self, price: float) -> int:
        """Round price to the nearest instrument tick size."""
        ticks = round(price / self.tick_size_paise)
        return int(ticks * self.tick_size_paise)

    def reset_state(self) -> None:
        """Reset intraday breakout state to enable new entries."""
        self.in_trade = False
        self.trade_completed = False
        self.entry_side = None
        self.entry_price_paise = 0
        self.target_price_paise = 0
        self.stop_loss_price_paise = 0
        self.highest_price_paise = 0
        self.lowest_price_paise = 0
        self.log_signal(Side.BUY, self.last_ltp_paise.get(self.symbol, 0), "Breakout strategy cycle reset by user")

    def get_parameters(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "breakout_pct": round(self.breakout_pct * 100, 2),
            "target_pct": round(self.target_pct * 100, 2),
            "stop_loss_pct": round(self.stop_loss_pct * 100, 2),
            "direction": self.direction,
            "trailing_stop_pct": round(self.trailing_stop_pct * 100, 2) if self.trailing_stop_pct is not None else None,
        }

    def update_parameters(self, params: dict[str, Any]) -> None:
        if "symbol" in params and params["symbol"]:
            self.symbol = str(params["symbol"]).upper()
            self.symbols = [self.symbol]
        if "quantity" in params and int(params["quantity"]) > 0:
            self.quantity = int(params["quantity"])
        if "breakout_pct" in params and float(params["breakout_pct"]) > 0:
            self.breakout_pct = float(params["breakout_pct"]) / 100.0
        if "target_pct" in params and float(params["target_pct"]) > 0:
            self.target_pct = float(params["target_pct"]) / 100.0
        if "stop_loss_pct" in params and float(params["stop_loss_pct"]) > 0:
            self.stop_loss_pct = float(params["stop_loss_pct"]) / 100.0
        if "direction" in params and params["direction"]:
            self.direction = str(params["direction"]).upper()
        if "trailing_stop_pct" in params:
            val = params["trailing_stop_pct"]
            self.trailing_stop_pct = float(val) / 100.0 if val is not None and float(val) > 0 else None

    def on_tick(self, tick: Tick) -> list[OrderIntent]:
        if self.status != StrategyStatus.RUNNING or tick.symbol.upper() != self.symbol:
            return []

        self.update_ltp(tick.symbol, tick.ltp_paise)

        # Set open price from first tick if not preset
        if self.open_price_paise is None and tick.open_paise > 0:
            self.open_price_paise = tick.open_paise
        elif self.open_price_paise is None and tick.ltp_paise > 0:
            self.open_price_paise = tick.ltp_paise

        if self.trade_completed or self.open_price_paise is None:
            return []

        intents: list[OrderIntent] = []
        ltp = tick.ltp_paise

        # 1. Looking for Entry: breakout from open
        if not self.in_trade:
            buy_threshold = int(self.open_price_paise * (1 + self.breakout_pct))
            sell_threshold = int(self.open_price_paise * (1 - self.breakout_pct))

            allow_long = self.direction in ("BOTH", "LONG_ONLY")
            allow_short = self.direction in ("BOTH", "SHORT_ONLY")

            if allow_long and ltp >= buy_threshold:
                self.in_trade = True
                self.entry_side = Side.BUY
                self.highest_price_paise = ltp
                intents.append(
                    OrderIntent(
                        strategy_id=self.strategy_id,
                        symbol=self.symbol,
                        exchange=self.exchange,
                        side=Side.BUY,
                        quantity=self.quantity,
                        price_paise=self._round_to_tick(ltp),
                        product=Product.INTRADAY,
                        book=Book.RL,
                        validity=Validity.DAY,
                        tag="breakout_buy_entry",
                    )
                )
                self.log_signal(Side.BUY, ltp, f"Breakout BUY triggered (+{self.breakout_pct*100:.1f}% from Open ₹{self.open_price_paise/100:.2f})")
            elif allow_short and ltp <= sell_threshold:
                self.in_trade = True
                self.entry_side = Side.SELL
                self.lowest_price_paise = ltp
                intents.append(
                    OrderIntent(
                        strategy_id=self.strategy_id,
                        symbol=self.symbol,
                        exchange=self.exchange,
                        side=Side.SELL,
                        quantity=self.quantity,
                        price_paise=self._round_to_tick(ltp),
                        product=Product.INTRADAY,
                        book=Book.RL,
                        validity=Validity.DAY,
                        tag="breakout_sell_entry",
                    )
                )
                self.log_signal(Side.SELL, ltp, f"Breakout SELL triggered (-{self.breakout_pct*100:.1f}% from Open ₹{self.open_price_paise/100:.2f})")

        # 2. In Trade: Monitor Target & Stop-loss (with Trailing SL support)
        elif self.in_trade and self.entry_price_paise > 0:
            exit_triggered = False
            exit_reason = ""

            if self.entry_side == Side.BUY:
                # Update high watermark for trailing stop
                if ltp > self.highest_price_paise:
                    self.highest_price_paise = ltp
                    if self.trailing_stop_pct:
                        trail_sl = self._round_to_tick(self.highest_price_paise * (1 - self.trailing_stop_pct))
                        if trail_sl > self.stop_loss_price_paise:
                            self.stop_loss_price_paise = trail_sl

                if ltp >= self.target_price_paise:
                    exit_triggered = True
                    exit_reason = "target_hit"
                elif ltp <= self.stop_loss_price_paise:
                    exit_triggered = True
                    exit_reason = "stop_loss_hit"

                if exit_triggered:
                    self.trade_completed = True
                    self.in_trade = False
                    intents.append(
                        OrderIntent(
                            strategy_id=self.strategy_id,
                            symbol=self.symbol,
                            exchange=self.exchange,
                            side=Side.SELL,
                            quantity=self.quantity,
                            price_paise=self._round_to_tick(ltp),
                            product=Product.INTRADAY,
                            book=Book.RL,
                            validity=Validity.DAY,
                            tag=f"breakout_{exit_reason}",
                        )
                    )
                    note = f"Breakout Exit: Target (+{self.target_pct*100:.1f}%) hit" if exit_reason == "target_hit" else f"Breakout Exit: Stop-loss (-{self.stop_loss_pct*100:.1f}%) hit"
                    self.log_signal(Side.SELL, ltp, note)

            elif self.entry_side == Side.SELL:
                # Update low watermark for trailing stop
                if self.lowest_price_paise == 0 or ltp < self.lowest_price_paise:
                    self.lowest_price_paise = ltp
                    if self.trailing_stop_pct:
                        trail_sl = self._round_to_tick(self.lowest_price_paise * (1 + self.trailing_stop_pct))
                        if trail_sl < self.stop_loss_price_paise:
                            self.stop_loss_price_paise = trail_sl

                if ltp <= self.target_price_paise:
                    exit_triggered = True
                    exit_reason = "target_hit"
                elif ltp >= self.stop_loss_price_paise:
                    exit_triggered = True
                    exit_reason = "stop_loss_hit"

                if exit_triggered:
                    self.trade_completed = True
                    self.in_trade = False
                    intents.append(
                        OrderIntent(
                            strategy_id=self.strategy_id,
                            symbol=self.symbol,
                            exchange=self.exchange,
                            side=Side.BUY,
                            quantity=self.quantity,
                            price_paise=self._round_to_tick(ltp),
                            product=Product.INTRADAY,
                            book=Book.RL,
                            validity=Validity.DAY,
                            tag=f"breakout_{exit_reason}",
                        )
                    )
                    note = f"Breakout Exit: Target (-{self.target_pct*100:.1f}%) hit" if exit_reason == "target_hit" else f"Breakout Exit: Stop-loss (+{self.stop_loss_pct*100:.1f}%) hit"
                    self.log_signal(Side.BUY, ltp, note)

        return intents

    def on_fill(self, fill: TradeFill) -> None:
        super().on_fill(fill)
        # Compute target and stop-loss upon entry fill
        if self.entry_price_paise == 0:
            self.entry_price_paise = fill.price_paise
            if fill.side == Side.BUY:
                self.target_price_paise = self._round_to_tick(self.entry_price_paise * (1 + self.target_pct))
                self.stop_loss_price_paise = self._round_to_tick(self.entry_price_paise * (1 - self.stop_loss_pct))
                self.highest_price_paise = fill.price_paise
            else:
                self.target_price_paise = self._round_to_tick(self.entry_price_paise * (1 - self.target_pct))
                self.stop_loss_price_paise = self._round_to_tick(self.entry_price_paise * (1 + self.stop_loss_pct))
                self.lowest_price_paise = fill.price_paise

    def on_candle(self, candle: Candle) -> list[OrderIntent]:
        return []
