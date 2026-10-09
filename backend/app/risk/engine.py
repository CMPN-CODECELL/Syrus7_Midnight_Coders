from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from app.core.config import Settings, get_settings
from app.core.enums import RiskReason, Severity, Side, StrategyStatus
from app.market_data.instruments import InstrumentRegistry, get_instrument_registry
from app.risk.models import AccountRiskConfig, RiskAuditEntry, RiskCheckResult, RiskConfig
from app.strategies.base import BaseStrategy
from app.strategies.intents import OrderIntent


class RiskEngine:
    """Platform risk gatekeeper (L3).

    Enforces per-strategy and account-level limits:
    - Maximum daily loss (auto-halts strategy or triggers platform emergency)
    - Maximum position size (including in-flight / working orders)
    - Maximum orders per minute (sliding rate window)
    - Runaway strategy loop detection (auto-halts buggy strategies)
    - Pre-trade exchange sanity checks (freeze qty, tick size, circuits, lot size)
    - Global kill switch state
    - Complete audit log of all risk evaluations
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        registry: Optional[InstrumentRegistry] = None,
        default_config: Optional[RiskConfig] = None,
        account_config: Optional[AccountRiskConfig] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.registry = registry or get_instrument_registry()
        self.default_config = default_config or RiskConfig()
        self.account_config = account_config or AccountRiskConfig()

        self._strategy_configs: dict[str, RiskConfig] = {}
        # Sliding rate limit windows: strategy_id -> deque of UTC datetimes
        self._order_history: dict[str, deque[datetime]] = {}
        # Global order timestamps across all strategies for account rate limiting
        self._account_order_history: deque[datetime] = deque()

        # Runaway breach counter per strategy: strategy_id -> count of consecutive breaches
        self._breach_counts: dict[str, int] = {}

        # In-flight working orders: strategy_id -> {client_order_id: {"symbol": str, "side": Side, "quantity": int}}
        self._inflight_orders: dict[str, dict[str, dict[str, Any]]] = {}

        self.kill_switch_active: bool = False

        # In-memory audit trail (last 1000 evaluations)
        self._audit_log: deque[RiskAuditEntry] = deque(maxlen=1000)

        # Statistics
        self._total_evaluated: int = 0
        self._total_passed: int = 0
        self._total_rejected: int = 0
        self._rejections_by_reason: dict[str, int] = {}

    def set_strategy_config(self, strategy_id: str, config: RiskConfig) -> None:
        """Assign or override risk configuration for a specific strategy."""
        self._strategy_configs[strategy_id] = config

    def get_strategy_config(self, strategy_id: str) -> RiskConfig:
        """Get effective risk configuration for a strategy."""
        return self._strategy_configs.get(strategy_id, self.default_config)

    def set_account_config(self, config: AccountRiskConfig) -> None:
        """Update platform-wide account risk constraints."""
        self.account_config = config

    # ---------- In-Flight Order Management (Open Order Risk) ----------

    def register_inflight_order(
        self,
        strategy_id: str,
        client_order_id: str,
        symbol: str,
        side: Side,
        quantity: int,
        price_paise: int = 0,
    ) -> None:
        """Track an order that has passed risk and been submitted to broker."""
        if strategy_id not in self._inflight_orders:
            self._inflight_orders[strategy_id] = {}
        self._inflight_orders[strategy_id][client_order_id] = {
            "symbol": symbol.upper(),
            "side": side,
            "quantity": quantity,
            "price_paise": price_paise,
        }

    def release_inflight_order(
        self,
        strategy_id: str,
        client_order_id: str,
        filled_qty: Optional[int] = None,
    ) -> None:
        """Release or decrement working quantity once filled, rejected, or cancelled."""
        strat_inflight = self._inflight_orders.get(strategy_id)
        if not strat_inflight or client_order_id not in strat_inflight:
            return

        if filled_qty is not None and filled_qty > 0:
            current_qty = strat_inflight[client_order_id]["quantity"]
            if current_qty > filled_qty:
                # Partial fill: update remaining working quantity
                strat_inflight[client_order_id]["quantity"] = current_qty - filled_qty
                return

        # Complete fill, cancel, or rejection: remove completely
        strat_inflight.pop(client_order_id, None)

    def get_inflight_quantity(self, strategy_id: str, symbol: str) -> int:
        """Return net in-flight quantity (+qty for Buy, -qty for Sell) for a strategy."""
        strat_inflight = self._inflight_orders.get(strategy_id, {})
        sym_upper = symbol.upper()
        net = 0
        for order in strat_inflight.values():
            if order["symbol"] == sym_upper:
                if order["side"] == Side.BUY:
                    net += order["quantity"]
                else:
                    net -= order["quantity"]
        return net

    def clear_all_inflight(self) -> None:
        """Clear all in-flight tracking (e.g. on emergency kill switch)."""
        self._inflight_orders.clear()

    # ---------- Core Risk Evaluation Gateway ----------

    def evaluate_intent(
        self,
        intent: OrderIntent,
        strategy: BaseStrategy,
        current_time: Optional[datetime] = None,
    ) -> RiskCheckResult:
        """Evaluate an order intent against all platform risk limits (L3)."""
        now = current_time or datetime.now(timezone.utc)
        config = self.get_strategy_config(strategy.strategy_id)
        self._total_evaluated += 1

        # 1. Kill Switch Check
        if self.kill_switch_active:
            return self._record_decision(
                intent,
                RiskCheckResult(
                    passed=False,
                    reason=RiskReason.KILL_SWITCH_ACTIVE,
                    message="Trading halted: Kill switch is currently active",
                    severity=Severity.CRITICAL,
                ),
            )

        # 2. Strategy Status Check
        if strategy.status != StrategyStatus.RUNNING:
            return self._record_decision(
                intent,
                RiskCheckResult(
                    passed=False,
                    reason=RiskReason.SYMBOL_HALTED,
                    message=f"Strategy {strategy.strategy_id} is in status {strategy.status.value}",
                    severity=Severity.WARN,
                ),
            )

        # 3. Defensive Parameter Validation (Guards against buggy bot outputs)
        if intent.quantity <= 0:
            return self._record_decision(
                intent,
                RiskCheckResult(
                    passed=False,
                    reason=RiskReason.LOT_SIZE_INVALID,
                    message=f"Invalid quantity {intent.quantity}: order quantity must be positive",
                    severity=Severity.ERROR,
                ),
            )

        if intent.quantity > config.max_order_quantity:
            return self._record_decision(
                intent,
                RiskCheckResult(
                    passed=False,
                    reason=RiskReason.MAX_POSITION_SIZE_EXCEEDED,
                    message=(
                        f"Order quantity {intent.quantity} exceeds maximum allowed single order "
                        f"limit of {config.max_order_quantity}"
                    ),
                    severity=Severity.WARN,
                ),
            )

        if intent.price_paise < 0:
            return self._record_decision(
                intent,
                RiskCheckResult(
                    passed=False,
                    reason=RiskReason.TICK_SIZE_INVALID,
                    message=f"Negative order price {intent.price_paise} paise is not valid",
                    severity=Severity.ERROR,
                ),
            )

        # 4. Rate Limit & Runaway Strategy Loop Check
        rate_window = timedelta(seconds=self.settings.rate_window_seconds)
        if strategy.strategy_id not in self._order_history:
            self._order_history[strategy.strategy_id] = deque()

        history = self._order_history[strategy.strategy_id]
        # Evict timestamps older than the sliding rate window
        while history and (now - history[0]) > rate_window:
            history.popleft()

        if len(history) >= config.max_orders_per_minute:
            # Increment runaway breach counter
            self._breach_counts[strategy.strategy_id] = (
                self._breach_counts.get(strategy.strategy_id, 0) + 1
            )
            breaches = self._breach_counts[strategy.strategy_id]

            if breaches >= config.max_runaway_breaches:
                # Platform auto-halts runaway buggy strategy loop
                strategy.halt()
                return self._record_decision(
                    intent,
                    RiskCheckResult(
                        passed=False,
                        reason=RiskReason.MAX_ORDERS_PER_MINUTE_EXCEEDED,
                        message=(
                            f"Runaway loop detected: strategy breached rate limit {breaches} consecutive times "
                            f"(limit: {config.max_orders_per_minute}/min). Strategy HALTED automatically."
                        ),
                        severity=Severity.CRITICAL,
                    ),
                )

            return self._record_decision(
                intent,
                RiskCheckResult(
                    passed=False,
                    reason=RiskReason.MAX_ORDERS_PER_MINUTE_EXCEEDED,
                    message=(
                        f"Rate limit exceeded: {len(history)} orders in the last "
                        f"{self.settings.rate_window_seconds}s (limit: {config.max_orders_per_minute})"
                    ),
                    severity=Severity.WARN,
                ),
            )

        # Successful check resets runaway breach counter
        self._breach_counts[strategy.strategy_id] = 0

        # Global Account Rate Limit
        while self._account_order_history and (now - self._account_order_history[0]) > rate_window:
            self._account_order_history.popleft()

        if len(self._account_order_history) >= self.account_config.max_account_orders_per_minute:
            return self._record_decision(
                intent,
                RiskCheckResult(
                    passed=False,
                    reason=RiskReason.MAX_ORDERS_PER_MINUTE_EXCEEDED,
                    message=(
                        f"Platform aggregate rate limit reached: {len(self._account_order_history)} "
                        f"orders across all strategies in last {self.settings.rate_window_seconds}s "
                        f"(account limit: {self.account_config.max_account_orders_per_minute})"
                    ),
                    severity=Severity.WARN,
                ),
            )

        # 5. Max Daily Loss Check
        current_pnl = (
            strategy.net_pnl_paise
            if self.settings.daily_loss_mode == "net"
            else strategy.realized_pnl_paise
        )

        if current_pnl <= -config.max_daily_loss_paise:
            # Platform auto-halts runaway strategy
            strategy.halt()
            return self._record_decision(
                intent,
                RiskCheckResult(
                    passed=False,
                    reason=RiskReason.MAX_DAILY_LOSS_EXCEEDED,
                    message=(
                        f"Daily loss limit exceeded: loss is Rs.{-current_pnl/100:.2f} "
                        f"(limit: Rs.{config.max_daily_loss_paise/100:.2f}). Strategy halted."
                    ),
                    severity=Severity.CRITICAL,
                ),
            )

        # 6. Max Position Size Check (including in-flight working orders)
        current_net_qty = strategy.get_position(intent.symbol)
        inflight_net = (
            self.get_inflight_quantity(strategy.strategy_id, intent.symbol)
            if config.include_inflight_orders
            else 0
        )
        effective_existing_qty = current_net_qty + inflight_net

        qty_change = intent.quantity if intent.side == Side.BUY else -intent.quantity
        projected_net_qty = effective_existing_qty + qty_change

        if abs(projected_net_qty) > config.max_position_size:
            msg = (
                f"Position limit exceeded: current pos={current_net_qty}, "
                f"in-flight={inflight_net}, order={qty_change} -> "
                f"projected position would be {abs(projected_net_qty)} units "
                f"(limit: {config.max_position_size} units)"
            )
            return self._record_decision(
                intent,
                RiskCheckResult(
                    passed=False,
                    reason=RiskReason.MAX_POSITION_SIZE_EXCEEDED,
                    message=msg,
                    severity=Severity.WARN,
                ),
            )

        # 7. Pre-trade Exchange Sanity Checks (Cheap checks before hitting broker)
        if config.enforce_pre_trade_sanity:
            inst = self.registry.find_by_symbol(intent.symbol, intent.exchange)
            if not inst:
                return self._record_decision(
                    intent,
                    RiskCheckResult(
                        passed=False,
                        reason=RiskReason.SYMBOL_HALTED,
                        message=f"Instrument {intent.symbol} ({intent.exchange.value}) not found in registry",
                        severity=Severity.ERROR,
                    ),
                )

            # Freeze quantity check
            if inst.freeze_quantity > 0 and intent.quantity > inst.freeze_quantity:
                return self._record_decision(
                    intent,
                    RiskCheckResult(
                        passed=False,
                        reason=RiskReason.FREEZE_QUANTITY_EXCEEDED,
                        message=f"Order quantity {intent.quantity} exceeds exchange freeze limit {inst.freeze_quantity}",
                        severity=Severity.ERROR,
                    ),
                )

            # Lot size check
            if inst.lot_size > 1 and (intent.quantity % inst.lot_size != 0):
                return self._record_decision(
                    intent,
                    RiskCheckResult(
                        passed=False,
                        reason=RiskReason.LOT_SIZE_INVALID,
                        message=f"Quantity {intent.quantity} must be a multiple of lot size {inst.lot_size}",
                        severity=Severity.ERROR,
                    ),
                )

            # Tick size check for limit orders
            if intent.price_paise > 0 and inst.tick_size_paise > 0:
                if intent.price_paise % inst.tick_size_paise != 0:
                    return self._record_decision(
                        intent,
                        RiskCheckResult(
                            passed=False,
                            reason=RiskReason.TICK_SIZE_INVALID,
                            message=(
                                f"Price Rs.{intent.price_paise/100:.2f} is not a valid multiple "
                                f"of tick size Rs.{inst.tick_size_paise/100:.2f}"
                            ),
                            severity=Severity.ERROR,
                        ),
                    )

            # Circuit limits check for limit orders
            if intent.price_paise > 0 and (inst.lower_circuit_paise > 0 or inst.upper_circuit_paise > 0):
                if intent.price_paise < inst.lower_circuit_paise or intent.price_paise > inst.upper_circuit_paise:
                    return self._record_decision(
                        intent,
                        RiskCheckResult(
                            passed=False,
                            reason=RiskReason.PRICE_OUTSIDE_CIRCUIT,
                            message=(
                                f"Price Rs.{intent.price_paise/100:.2f} outside circuit limits "
                                f"[Rs.{inst.lower_circuit_paise/100:.2f}, Rs.{inst.upper_circuit_paise/100:.2f}]"
                            ),
                            severity=Severity.ERROR,
                        ),
                    )

        # Order passes all risk checks -> record timestamps
        history.append(now)
        self._account_order_history.append(now)

        return self._record_decision(
            intent,
            RiskCheckResult(passed=True, message="Order approved by Risk Engine"),
        )

    # ---------- Auditing & Diagnostics ----------

    def _record_decision(self, intent: OrderIntent, result: RiskCheckResult) -> RiskCheckResult:
        """Internal recorder for audit logging and metrics."""
        if result.passed:
            self._total_passed += 1
        else:
            self._total_rejected += 1
            reason_key = result.reason.value if result.reason else "UNKNOWN"
            self._rejections_by_reason[reason_key] = (
                self._rejections_by_reason.get(reason_key, 0) + 1
            )

        self._audit_log.append(
            RiskAuditEntry(
                timestamp=datetime.now(timezone.utc),
                strategy_id=intent.strategy_id,
                symbol=intent.symbol,
                side=intent.side.value,
                quantity=intent.quantity,
                price_paise=intent.price_paise,
                passed=result.passed,
                reason=result.reason,
                message=result.message,
                severity=result.severity,
            )
        )
        return result

    def get_audit_log(
        self,
        limit: int = 50,
        strategy_id: Optional[str] = None,
        passed_only: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve recent risk evaluations for monitoring dashboard."""
        logs = list(self._audit_log)
        if strategy_id:
            logs = [e for e in logs if e.strategy_id == strategy_id]
        if passed_only is not None:
            logs = [e for e in logs if e.passed == passed_only]

        return [entry.model_dump() for entry in logs[-limit:]]

    def get_risk_metrics(self) -> dict[str, Any]:
        """Summary metrics of platform risk performance."""
        return {
            "total_evaluated": self._total_evaluated,
            "total_passed": self._total_passed,
            "total_rejected": self._total_rejected,
            "rejection_rate_pct": (
                round((self._total_rejected / self._total_evaluated) * 100, 2)
                if self._total_evaluated > 0
                else 0.0
            ),
            "rejections_by_reason": dict(self._rejections_by_reason),
            "kill_switch_active": self.kill_switch_active,
            "active_inflight_orders_count": sum(
                len(orders) for orders in self._inflight_orders.values()
            ),
        }
