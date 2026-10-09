from typing import Any
from app.broker.models import TradeFill
from app.core.enums import StrategyStatus, Timeframe
from app.market_data.candle import Candle, CandleAggregator, Tick
from app.strategies.base import BaseStrategy
from app.strategies.intents import OrderIntent


class StrategyManager:
    """Manages the lifecycle, subscriptions, tick routing, and position isolation

    for multiple strategies running concurrently on a single account (L1, L4).
    """

    def __init__(self) -> None:
        # Active strategies by strategy_id
        self._strategies: dict[str, BaseStrategy] = {}

        # User subscriptions: user_id -> set of strategy_ids
        self._user_subscriptions: dict[str, set[str]] = {}

        # Candle aggregators for 1m and 5m
        self.aggregator_1m = CandleAggregator(Timeframe.M1, on_candle_closed=self._on_candle_closed)
        self.aggregator_5m = CandleAggregator(Timeframe.M5, on_candle_closed=self._on_candle_closed)

        # Queued candle intents
        self._pending_candle_intents: list[OrderIntent] = []

    def register_strategy(self, strategy: BaseStrategy) -> None:
        """Register a strategy instance into the platform."""
        self._strategies[strategy.strategy_id] = strategy

    def unregister_strategy(self, strategy_id: str) -> None:
        """Remove a strategy."""
        if strategy_id in self._strategies:
            self._strategies[strategy_id].stop()
            del self._strategies[strategy_id]

    def get_strategy(self, strategy_id: str) -> BaseStrategy | None:
        """Get strategy by ID."""
        return self._strategies.get(strategy_id)

    def list_strategies(self) -> list[BaseStrategy]:
        """List all registered strategies."""
        return list(self._strategies.values())

    def reset_strategy(self, strategy_id: str) -> bool:
        """Reset internal trade cycle state for a strategy."""
        strat = self._strategies.get(strategy_id)
        if strat:
            strat.reset_state()
            return True
        return False

    def update_strategy_parameters(self, strategy_id: str, params: dict[str, Any]) -> bool:
        """Update runtime parameters of a registered strategy."""
        strat = self._strategies.get(strategy_id)
        if strat:
            strat.update_parameters(params)
            return True
        return False

    # ---------- User Subscriptions (L1) ----------

    def subscribe(self, user_id: str, strategy_id: str) -> bool:
        """Subscribe a user to a strategy."""
        if strategy_id not in self._strategies:
            return False
        if user_id not in self._user_subscriptions:
            self._user_subscriptions[user_id] = set()
        self._user_subscriptions[user_id].add(strategy_id)
        return True

    def unsubscribe(self, user_id: str, strategy_id: str) -> bool:
        """Unsubscribe a user from a strategy."""
        if user_id in self._user_subscriptions:
            self._user_subscriptions[user_id].discard(strategy_id)
            return True
        return False

    def get_user_strategies(self, user_id: str) -> list[BaseStrategy]:
        """Get all strategies a user is subscribed to."""
        strat_ids = self._user_subscriptions.get(user_id, set())
        return [self._strategies[sid] for sid in strat_ids if sid in self._strategies]

    # ---------- Market Data & Tick Routing (L1, L4) ----------

    def _on_candle_closed(self, candle: Candle) -> None:
        """Callback when a 1m or 5m candle closes."""
        for strat in self._strategies.values():
            if strat.status == StrategyStatus.RUNNING:
                intents = strat.on_candle(candle)
                self._pending_candle_intents.extend(intents)

    def route_tick(self, tick: Tick) -> list[OrderIntent]:
        """Feed tick to candle aggregators and active strategies, returning any order intents."""
        self._pending_candle_intents.clear()

        # Update 1m and 5m candle aggregators
        self.aggregator_1m.process_tick(tick)
        self.aggregator_5m.process_tick(tick)

        intents: list[OrderIntent] = list(self._pending_candle_intents)

        # Dispatch tick to each running strategy interested in this symbol
        sym = tick.symbol.upper()
        for strat in self._strategies.values():
            if strat.status == StrategyStatus.RUNNING and (not strat.symbols or sym in strat.symbols):
                tick_intents = strat.on_tick(tick)
                intents.extend(tick_intents)

        return intents

    # ---------- Order & Fill Routing (L2, L4) ----------

    def route_fill(self, strategy_id: str, fill: TradeFill) -> None:
        """Route an execution fill to the exact strategy that originated it (L4 isolation)."""
        strat = self._strategies.get(strategy_id)
        if strat:
            strat.on_fill(fill)

    # ---------- Platform Controls & Kill Switch (L3) ----------

    def start_all(self) -> None:
        """Start all registered strategies."""
        for strat in self._strategies.values():
            strat.start()

    def stop_all(self) -> None:
        """Stop all strategies."""
        for strat in self._strategies.values():
            strat.stop()

    def halt_all(self) -> None:
        """Emergency halt for all strategies (Kill switch invoked)."""
        for strat in self._strategies.values():
            strat.halt()

    # ---------- Portfolio & Positions Dashboard (L4) ----------

    def get_strategy_performance(self) -> list[dict[str, Any]]:
        """Return live P&L and position summary for each strategy."""
        summary = []
        for strat in self._strategies.values():
            summary.append(
                {
                    "strategy_id": strat.strategy_id,
                    "name": strat.name,
                    "status": strat.status.value,
                    "symbols": strat.symbols,
                    "realized_pnl_paise": strat.realized_pnl_paise,
                    "unrealized_pnl_paise": strat.unrealized_pnl_paise,
                    "total_charges_paise": strat.total_charges_paise,
                    "net_pnl_paise": strat.net_pnl_paise,
                    "positions": {
                        sym: data["net_qty"]
                        for sym, data in strat.positions.items()
                        if data["net_qty"] != 0
                    },
                    "total_fills": len(strat.fills),
                }
            )
        return summary
