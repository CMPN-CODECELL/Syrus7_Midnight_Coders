from collections import deque
from datetime import time
from typing import Any
from zoneinfo import ZoneInfo

from app.broker.models import TradeFill
from app.core.enums import Book, Exchange, Product, Side, StrategyStatus, Timeframe, Validity
from app.market_data.candle import Candle, Tick
from app.strategies.base import BaseStrategy
from app.strategies.intents import OrderIntent


class MovingAverageCrossStrategy(BaseStrategy):
    """Strategy 3: Dual Moving Average Crossover on 1m/5m Candles with custom parameters.

    Rules:
    1. Operates on closed candles of the specified timeframe (1m or 5m).
    2. Computes Fast SMA and Slow SMA on candle close.
    3. Entry:
       - Fast SMA crosses ABOVE Slow SMA: BUY entry with INTRADAY product.
    4. Exit:
       - Fast SMA crosses BELOW Slow SMA: Close long position.
       - Risk exit: Take-profit or stop-loss hit on live tick.
       - Time exit: Automatically squares off at configured exit time (default 3:15 PM IST).
    5. Fully customizable parameters: fast/slow periods, targets, SL, size, symbol.
    """

    def __init__(
        self,
        strategy_id: str | None = None,
        name: str = "MACrossStrategy",
        symbol: str = "TCS",
        exchange: Exchange = Exchange.NSE,
        quantity: int = 5,
        timeframe: Timeframe = Timeframe.M1,
        fast_period: int = 5,
        slow_period: int = 20,
        take_profit_pct: float = 0.02,  # +2%
        stop_loss_pct: float = 0.01,    # -1%
        exit_time: time = time(15, 15),
        timezone_str: str = "Asia/Kolkata",
    ) -> None:
        super().__init__(strategy_id=strategy_id, name=name, symbols=[symbol])
        self.symbol = symbol.upper()
        self.exchange = exchange
        self.quantity = quantity
        self.timeframe = timeframe
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.exit_time = exit_time
        self.tz = ZoneInfo(timezone_str)

        # Candle close history
        self.closes: deque[int] = deque(maxlen=slow_period + 10)
        self.prev_fast_sma: float | None = None
        self.prev_slow_sma: float | None = None

        self.in_trade: bool = False
        self.entry_price_paise: int = 0

    def reset_state(self) -> None:
        """Reset trade state to allow fresh crossover entries."""
        self.in_trade = False
        self.entry_price_paise = 0
        self.log_signal(Side.BUY, self.last_ltp_paise.get(self.symbol, 0), "MA Crossover cycle reset by user")

    def get_parameters(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "timeframe": self.timeframe.value if hasattr(self.timeframe, "value") else str(self.timeframe),
            "fast_period": self.fast_period,
            "slow_period": self.slow_period,
            "take_profit_pct": round(self.take_profit_pct * 100, 2),
            "stop_loss_pct": round(self.stop_loss_pct * 100, 2),
            "exit_time": self.exit_time.strftime("%H:%M") if hasattr(self.exit_time, "strftime") else str(self.exit_time),
        }

    def update_parameters(self, params: dict[str, Any]) -> None:
        if "symbol" in params and params["symbol"]:
            self.symbol = str(params["symbol"]).upper()
            self.symbols = [self.symbol]
        if "quantity" in params and int(params["quantity"]) > 0:
            self.quantity = int(params["quantity"])
        if "timeframe" in params:
            tf = str(params["timeframe"]).lower()
            self.timeframe = Timeframe.M5 if tf in ("5m", "m5") else Timeframe.M1
        if "fast_period" in params and int(params["fast_period"]) > 0:
            self.fast_period = int(params["fast_period"])
        if "slow_period" in params and int(params["slow_period"]) > 0:
            self.slow_period = int(params["slow_period"])
            # Adjust deque capacity
            self.closes = deque(self.closes, maxlen=self.slow_period + 10)
        if "take_profit_pct" in params and float(params["take_profit_pct"]) > 0:
            self.take_profit_pct = float(params["take_profit_pct"]) / 100.0
        if "stop_loss_pct" in params and float(params["stop_loss_pct"]) > 0:
            self.stop_loss_pct = float(params["stop_loss_pct"]) / 100.0
        if "exit_time" in params:
            parts = str(params["exit_time"]).split(":")
            self.exit_time = time(int(parts[0]), int(parts[1]))

    def on_tick(self, tick: Tick) -> list[OrderIntent]:
        if self.status != StrategyStatus.RUNNING or tick.symbol.upper() != self.symbol:
            return []

        self.update_ltp(tick.symbol, tick.ltp_paise)
        intents: list[OrderIntent] = []

        if not self.in_trade or self.entry_price_paise == 0:
            return []

        ltp = tick.ltp_paise
        local_dt = tick.timestamp.astimezone(self.tz)

        # 1. Take-profit check
        tp_price = int(self.entry_price_paise * (1 + self.take_profit_pct))
        if ltp >= tp_price:
            self.in_trade = False
            intents.append(self._create_exit_intent(ltp, "take_profit"))
            self.log_signal(Side.SELL, ltp, f"Take-Profit (+{self.take_profit_pct*100:.1f}%) hit")
            return intents

        # 2. Stop-loss check
        sl_price = int(self.entry_price_paise * (1 - self.stop_loss_pct))
        if ltp <= sl_price:
            self.in_trade = False
            intents.append(self._create_exit_intent(ltp, "stop_loss"))
            self.log_signal(Side.SELL, ltp, f"Stop-Loss (-{self.stop_loss_pct*100:.1f}%) hit")
            return intents

        # 3. Time exit check (default 3:15 PM IST)
        if local_dt.time() >= self.exit_time:
            self.in_trade = False
            intents.append(self._create_exit_intent(ltp, "time_exit"))
            self.log_signal(Side.SELL, ltp, f"Square-off at exit time {self.exit_time.strftime('%H:%M')}")
            return intents

        return intents

    def on_candle(self, candle: Candle) -> list[OrderIntent]:
        if self.status != StrategyStatus.RUNNING:
            return []
        if candle.symbol.upper() != self.symbol or candle.timeframe != self.timeframe or not candle.is_closed:
            return []

        self.closes.append(candle.close_paise)
        if len(self.closes) < self.slow_period:
            return []

        # Calculate SMAs
        fast_closes = list(self.closes)[-self.fast_period :]
        slow_closes = list(self.closes)[-self.slow_period :]
        fast_sma = sum(fast_closes) / self.fast_period
        slow_sma = sum(slow_closes) / self.slow_period

        intents: list[OrderIntent] = []

        if self.prev_fast_sma is not None and self.prev_slow_sma is not None:
            # Bullish Crossover: Fast crosses above Slow
            if self.prev_fast_sma <= self.prev_slow_sma and fast_sma > slow_sma:
                if not self.in_trade:
                    self.in_trade = True
                    intents.append(
                        OrderIntent(
                            strategy_id=self.strategy_id,
                            symbol=self.symbol,
                            exchange=self.exchange,
                            side=Side.BUY,
                            quantity=self.quantity,
                            price_paise=candle.close_paise,
                            product=Product.INTRADAY,
                            book=Book.RL,
                            validity=Validity.DAY,
                            tag="ma_golden_cross_buy",
                        )
                    )
                    self.log_signal(Side.BUY, candle.close_paise, f"Golden Crossover: Fast SMA ({self.fast_period}) crossed above Slow SMA ({self.slow_period})")

            # Bearish Crossover: Fast crosses below Slow
            elif self.prev_fast_sma >= self.prev_slow_sma and fast_sma < slow_sma:
                if self.in_trade:
                    self.in_trade = False
                    intents.append(self._create_exit_intent(candle.close_paise, "ma_death_cross_exit"))
                    self.log_signal(Side.SELL, candle.close_paise, f"Bearish Crossover: Fast SMA ({self.fast_period}) crossed below Slow SMA ({self.slow_period})")

        self.prev_fast_sma = fast_sma
        self.prev_slow_sma = slow_sma
        return intents

    def _create_exit_intent(self, price_paise: int, tag: str) -> OrderIntent:
        net_qty = self.get_position(self.symbol)
        qty = abs(net_qty) if net_qty != 0 else self.quantity
        return OrderIntent(
            strategy_id=self.strategy_id,
            symbol=self.symbol,
            exchange=self.exchange,
            side=Side.SELL,
            quantity=qty,
            price_paise=price_paise,
            product=Product.INTRADAY,
            book=Book.RL,
            validity=Validity.DAY,
            tag=f"ma_{tag}",
        )

    def on_fill(self, fill: TradeFill) -> None:
        super().on_fill(fill)
        if fill.side == Side.BUY and self.entry_price_paise == 0:
            self.entry_price_paise = fill.price_paise
        elif fill.side == Side.SELL:
            self.entry_price_paise = 0
