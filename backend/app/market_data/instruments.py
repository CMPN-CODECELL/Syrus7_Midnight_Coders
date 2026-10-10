import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.enums import EXCHANGE_TO_INSTRUMENT_NAME, Exchange


@dataclass(frozen=True)
class InstrumentInfo:
    token: int
    exchange: str
    symbol: str
    instrument_type: str
    tick_size_paise: int
    lot_size: int
    freeze_quantity: int
    lower_circuit_paise: int
    upper_circuit_paise: int
    isin: str


class InstrumentRegistry:
    """In-memory registry and lookup service for 021 exchange instruments.

    Loaded from instruments.csv once at startup.
    """

    def __init__(self, csv_path: str | Path | None = None) -> None:
        if csv_path is None:
            # Default to backend/instruments.csv
            base_dir = Path(__file__).resolve().parent.parent.parent
            csv_path = base_dir / "instruments.csv"
        self.csv_path = Path(csv_path)

        # Lookup maps
        # Key: (symbol.upper(), exchange_normalized_str)
        self._by_symbol_exchange: dict[tuple[str, str], InstrumentInfo] = {}
        # Key: (token, exchange_normalized_str)
        self._by_token: dict[int, InstrumentInfo] = {}
        self._loaded: bool = False

    def load(self) -> None:
        """Load instrument mappings from CSV file."""
        if self._loaded or not self.csv_path.exists():
            return

        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    token = int(row["token"])
                    exchange_str = row["exchange"].strip().upper()
                    symbol = row["symbol"].strip().upper()
                    inst_type = row["instrument_type"].strip().upper()
                    ticksize = int(row.get("ticksize", 5) or 5)
                    lot_size = int(row.get("board_lot_quantity", 1) or 1)
                    freeze_qty = int(row.get("freeze_quantity", 0) or 0)
                    lower_circ = int(row.get("lower_circuit", 0) or 0)
                    upper_circ = int(row.get("upper_circuit", 0) or 0)
                    isin = row.get("isin", "").strip()

                    info = InstrumentInfo(
                        token=token,
                        exchange=exchange_str,
                        symbol=symbol,
                        instrument_type=inst_type,
                        tick_size_paise=ticksize,
                        lot_size=lot_size,
                        freeze_quantity=freeze_qty,
                        lower_circuit_paise=lower_circ,
                        upper_circuit_paise=upper_circ,
                        isin=isin,
                    )

                    # Index by token
                    self._by_token[token] = info

                    # Index by (symbol, exchange)
                    # For equity stocks, STK instruments are prioritized
                    key = (symbol, exchange_str)
                    if key not in self._by_symbol_exchange or inst_type == "STK":
                        self._by_symbol_exchange[key] = info

                except (ValueError, KeyError):
                    continue

        self._loaded = True

    def find_by_symbol(self, symbol: str, exchange: Exchange | str = Exchange.NSE) -> Optional[InstrumentInfo]:
        """Find instrument by ticker symbol and exchange."""
        if not self._loaded:
            self.load()

        exch_key = exchange.value if isinstance(exchange, Exchange) else str(exchange).upper()
        # Map Exchange.NSE -> NSECM if needed
        internal_exch = EXCHANGE_TO_INSTRUMENT_NAME.get(Exchange(exch_key), exch_key) if exch_key in Exchange.__members__ else exch_key

        sym = symbol.strip().upper()
        # Check mapped internal exchange first, then direct key
        return (
            self._by_symbol_exchange.get((sym, internal_exch))
            or self._by_symbol_exchange.get((sym, exch_key))
        )

    def find_by_token(self, token: int) -> Optional[InstrumentInfo]:
        """Find instrument by token id."""
        if not self._loaded:
            self.load()
        return self._by_token.get(token)

    def list_all(self, limit: int = 100) -> list[InstrumentInfo]:
        """Return registered instruments, prioritizing top active equities."""
        if not self._loaded:
            self.load()
        key_symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "TATAMOTORS", "NIFTY50", "SBIN", "ICICIBANK", "ITC", "BHARTIARTL"]
        result: list[InstrumentInfo] = []
        seen_tokens: set[int] = set()

        for sym in key_symbols:
            inst = self.find_by_symbol(sym)
            if inst and inst.token not in seen_tokens:
                result.append(inst)
                seen_tokens.add(inst.token)

        for token, inst in self._by_token.items():
            if token not in seen_tokens:
                result.append(inst)
                seen_tokens.add(token)
            if len(result) >= limit:
                break

        return result


# Global singleton instance for easy access across the platform
_default_registry: Optional[InstrumentRegistry] = None


def get_instrument_registry() -> InstrumentRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = InstrumentRegistry()
        _default_registry.load()
    return _default_registry
