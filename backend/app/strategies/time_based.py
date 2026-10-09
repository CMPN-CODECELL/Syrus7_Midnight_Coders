from datetime import time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.broker.models import TradeFill
from app.core.enums import Book, Exchange, Product, Side, StrategyStatus, Validity
from app.market_data.candle import Candle, Tick
from app.strategies.base import BaseStrategy
from app.strategies.intents import OrderIntent


class TimeBasedStrategy(BaseStrategy):
    """Strategy 1: Customizable time-based intraday execution with target/stop-loss.

    Rules:
    1. At configured entry time (default 09:15 AM IST): Enter position for chosen symbol, side and quantity.
    2. Optional risk controls: Stop-Loss (%) and Target Profit (%) monitored on live ticks.
    3. At configured square-off time (default 15:15 PM IST): Automatically squares off open position.
    4. Provides full customizability for user to tweak times, risk targets, size, and direction.
    """

    def __init__(
        self,
        strategy_id: str | None = None,
        name: str = "TimeBasedStrategy",
        symbol: str = "RELIANCE",
        exchange: Exchange = Exchange.NSE,
        side: Side = Side.BUY,
        quantity: int = 10,
        entry_time: time = time(9, 15),
        exit_time: time = time(15, 15),
        stop_loss_pct: float | None = None,
        target_pct: float | None = None,
        timezone_str: str = "Asia/Kolkata",
    ) -> None:
        super().__init__(strategy_id=strategy_id, name=name, symbols=[symbol])
        self.symbol = symbol.upper()
        self.exchange = exchange
        self.side = side
        self.quantity = quantity
        self.entry_time = entry_time
        self.exit_time = exit_time
        self.stop_loss_pct = stop_loss_pct
        self.target_pct = target_pct
        self.tz = ZoneInfo(timezone_str)

        self.entered_today: bool = False
        self.exited_today: bool = False
        self.entry_price_paise: int = 0

    def on_fill(self, fill: TradeFill) -> None:
        super().on_fill(fill)
        if fill.symbol.upper() == self.symbol and self.get_position(self.symbol) != 0:
            self.entry_price_paise = fill.price_paise

    def reset_state(self) -> None:
        """Reset intraday flags to allow re-entering on demand."""
        self.entered_today = False
        self.exited_today = False
        self.entry_price_paise = 0
        self.log_signal(self.side, self.last_ltp_paise.get(self.symbol, 0), "Strategy intraday state reset by user")

    def get_parameters(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side.value if hasattr(self.side, "value") else str(self.side),
            "quantity": self.quantity,
            "entry_time": self.entry_time.strftime("%H:%M") if hasattr(self.entry_time, "strftime") else str(self.entry_time),
            "exit_time": self.exit_time.strftime("%H:%M") if hasattr(self.exit_time, "strftime") else str(self.exit_time),
            "stop_loss_pct": round(self.stop_loss_pct * 100, 2) if self.stop_loss_pct is not None else None,
            "target_pct": round(self.target_pct * 100, 2) if self.target_pct is not None else None,
        }

    def update_parameters(self, params: dict[str, Any]) -> None:
        if "symbol" in params and params["symbol"]:
            self.symbol = str(params["symbol"]).upper()
            self.symbols = [self.symbol]
        if "quantity" in params and int(params["quantity"]) > 0:
            self.quantity = int(params["quantity"])
        if "side" in params:
            s_val = str(params["side"]).upper()
            self.side = Side.BUY if "BUY" in s_val else Side.SELL
        if "entry_time" in params:
            parts = str(params["entry_time"]).split(":")
            self.entry_time = time(int(parts[0]), int(parts[1]))
        if "exit_time" in params:
            parts = str(params["exit_time"]).split(":")
            self.exit_time = time(int(parts[0]), int(parts[1]))
        if "stop_loss_pct" in params:
            val = params["stop_loss_pct"]
            self.stop_loss_pct = float(val) / 100.0 if val is not None and float(val) > 0 else None
        if "target_pct" in params:
            val = params["target_pct"]
            self.target_pct = float(val) / 100.0 if val is not None and float(val) > 0 else None

    def on_tick(self, tick: Tick) -> list[OrderIntent]:
        if self.status != StrategyStatus.RUNNING or tick.symbol.upper() != self.symbol:
            return []

        self.update_ltp(tick.symbol, tick.ltp_paise)
        local_dt = tick.timestamp.astimezone(self.tz)
        current_time = local_dt.time()
        intents: list[OrderIntent] = []

        # 1. Entry condition: configured entry time or later, not entered yet
        if not self.entered_today and current_time >= self.entry_time and current_time < self.exit_time:
            self.entered_today = True
            intent = OrderIntent(
                strategy_id=self.strategy_id,
                symbol=self.symbol,
                exchange=self.exchange,
                side=self.side,
                quantity=self.quantity,
                price_paise=0,  # Market order
                product=Product.INTRADAY,
                book=Book.RL,
                validity=Validity.DAY,
                tag="time_based_entry",
            )
            intents.append(intent)
            self.log_signal(self.side, tick.ltp_paise, f"Time Entry triggered at {current_time.strftime('%H:%M')}")
            return intents

        # 2. Risk checks while in position (Target or Stop-Loss hit)
        net_qty = self.get_position(self.symbol)
        if self.entered_today and not self.exited_today and net_qty != 0 and self.entry_price_paise > 0:
            ltp = tick.ltp_paise
            exit_side = Side.SELL if net_qty > 0 else Side.BUY
            is_long = net_qty > 0

            # Target check
            if self.target_pct:
                tp_hit = (ltp >= int(self.entry_price_paise * (1 + self.target_pct))) if is_long else (ltp <= int(self.entry_price_paise * (1 - self.target_pct)))
                if tp_hit:
                    self.exited_today = True
                    intents.append(
                        OrderIntent(
                            strategy_id=self.strategy_id,
                            symbol=self.symbol,
                            exchange=self.exchange,
                            side=exit_side,
                            quantity=abs(net_qty),
                            price_paise=0,
                            product=Product.INTRADAY,
                            book=Book.RL,
                            validity=Validity.DAY,
                            tag="time_based_target_hit",
                        )
                    )
                    self.log_signal(exit_side, ltp, f"Target Profit (+{self.target_pct*100:.1f}%) hit")
                    return intents

            # Stop-loss check
            if self.stop_loss_pct:
                sl_hit = (ltp <= int(self.entry_price_paise * (1 - self.stop_loss_pct))) if is_long else (ltp >= int(self.entry_price_paise * (1 + self.stop_loss_pct)))
                if sl_hit:
                    self.exited_today = True
                    intents.append(
                        OrderIntent(
                            strategy_id=self.strategy_id,
                            symbol=self.symbol,
                            exchange=self.exchange,
                            side=exit_side,
                            quantity=abs(net_qty),
                            price_paise=0,
                            product=Product.INTRADAY,
                            book=Book.RL,
                            validity=Validity.DAY,
                            tag="time_based_stop_loss_hit",
                        )
                    )
                    self.log_signal(exit_side, ltp, f"Stop-loss (-{self.stop_loss_pct*100:.1f}%) hit")
                    return intents

        # 3. Scheduled square-off exit
        if self.entered_today and not self.exited_today and current_time >= self.exit_time:
            if net_qty != 0:
                self.exited_today = True
                exit_side = Side.SELL if net_qty > 0 else Side.BUY
                intents.append(
                    OrderIntent(
                        strategy_id=self.strategy_id,
                        symbol=self.symbol,
                        exchange=self.exchange,
                        side=exit_side,
                        quantity=abs(net_qty),
                        price_paise=0,  # Market square off
                        product=Product.INTRADAY,
                        book=Book.RL,
                        validity=Validity.DAY,
                        tag="time_based_squareoff",
                    )
                )
                self.log_signal(exit_side, tick.ltp_paise, f"Scheduled Intraday Square-off at {current_time.strftime('%H:%M')}")

        return intents

    def on_candle(self, candle: Candle) -> list[OrderIntent]:
        return []
