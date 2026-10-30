"""Small, dependency-free shared contracts for research and paper simulation.

This module deliberately does not connect to exchanges or submit orders.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Mapping

from mi_core.costs import (
    ExecutionCostConfig,
    estimate_execution_cost,
    get_round_trip_cost_pct,
)


def _number(value: object, name: str, *, positive: bool = False,
            non_negative: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    if positive and result <= 0:
        raise ValueError(f"{name} must be positive")
    if non_negative and result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


@dataclass(frozen=True)
class CostModel:
    """Select exactly one cost convention; research and execution never stack."""

    mode: Literal["research_policy", "execution_components"] = "research_policy"
    policy: Literal["base", "strict"] | None = "base"
    execution_config: ExecutionCostConfig | None = None

    def __post_init__(self) -> None:
        if self.mode == "research_policy":
            if self.policy not in ("base", "strict") or self.execution_config is not None:
                raise ValueError(
                    "research_policy requires base/strict policy and no execution_config"
                )
        elif self.mode == "execution_components":
            if self.policy is not None:
                raise ValueError(
                    "execution_components requires policy=None; policies cannot be stacked"
                )
            if self.execution_config is not None and not isinstance(
                self.execution_config, ExecutionCostConfig
            ):
                raise TypeError("execution_config must be an ExecutionCostConfig")
        else:
            raise ValueError("unsupported cost model mode")

    @classmethod
    def research(cls, policy: Literal["base", "strict"] = "base") -> "CostModel":
        return cls(mode="research_policy", policy=policy)

    @classmethod
    def execution(
        cls, config: ExecutionCostConfig | None = None
    ) -> "CostModel":
        return cls(
            mode="execution_components",
            policy=None,
            execution_config=config if config is not None else ExecutionCostConfig(),
        )

    def cost_usd(self, notional_usd: float) -> float:
        notional = _number(notional_usd, "notional_usd", positive=True)
        if self.mode == "research_policy":
            assert self.policy is not None
            result = notional * get_round_trip_cost_pct(self.policy) / 100.0
        else:
            result = estimate_execution_cost(
                notional, config=self.execution_config
            ).total
        if not math.isfinite(result):
            raise ValueError("calculated cost must be finite")
        return result


@dataclass(frozen=True)
class Position:
    """Signed quantity: positive is long, negative is short."""

    symbol: str
    quantity: float
    entry_price: float

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        quantity = _number(self.quantity, "quantity")
        if quantity == 0:
            raise ValueError("quantity must be non-zero")
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(
            self, "entry_price", _number(self.entry_price, "entry_price", positive=True)
        )


@dataclass(frozen=True)
class PortfolioState:
    """Cash plus mark-to-market unrealized PnL for open signed positions."""

    cash_usd: float
    positions: tuple[Position, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "cash_usd", _number(self.cash_usd, "cash_usd"))
        positions = tuple(self.positions)
        if any(not isinstance(p, Position) for p in positions):
            raise TypeError("positions must contain only Position objects")
        symbols = [p.symbol for p in positions]
        if len(symbols) != len(set(symbols)):
            raise ValueError("duplicate position symbols are not allowed")
        object.__setattr__(self, "positions", positions)

    def equity(self, current_prices: Mapping[str, float]) -> float:
        if not isinstance(current_prices, Mapping):
            raise TypeError("current_prices must be a mapping")
        normalized: dict[str, float] = {}
        for raw_symbol, raw_price in current_prices.items():
            if not isinstance(raw_symbol, str) or not raw_symbol.strip():
                raise ValueError("price-map symbols must be non-empty strings")
            symbol = raw_symbol.strip().upper()
            if symbol in normalized:
                raise ValueError(f"duplicate normalized price symbol: {symbol}")
            normalized[symbol] = _number(
                raw_price, f"price for {symbol}", positive=True
            )

        required = {position.symbol for position in self.positions}
        missing = required - normalized.keys()
        extra = normalized.keys() - required
        if missing:
            raise ValueError(f"missing prices for: {', '.join(sorted(missing))}")
        if extra:
            raise ValueError(f"unexpected prices for: {', '.join(sorted(extra))}")

        unrealized = sum(
            position.quantity
            * (normalized[position.symbol] - position.entry_price)
            for position in self.positions
        )
        result = self.cash_usd + unrealized
        if not math.isfinite(result):
            raise ValueError("portfolio equity must be finite")
        return result


@dataclass(frozen=True)
class OrderIntent:
    """Validated research intent only; it is never an exchange order."""

    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    order_type: Literal["market", "limit"] = "market"
    limit_price: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        if self.side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        object.__setattr__(
            self, "quantity", _number(self.quantity, "quantity", positive=True)
        )
        if self.order_type == "market":
            if self.limit_price is not None:
                raise ValueError("market intent must not include limit_price")
        elif self.order_type == "limit":
            if self.limit_price is None:
                raise ValueError("limit intent requires limit_price")
            object.__setattr__(
                self, "limit_price",
                _number(self.limit_price, "limit_price", positive=True),
            )
        else:
            raise ValueError("order_type must be 'market' or 'limit'")


@dataclass(frozen=True)
class PlatformConfig:
    """Central research capital/economic settings with immutable safety gates."""

    capital_usd: float = 500.0
    min_profit_usd: float = 4.0
    preferred_profit_usd: float = 10.0
    cost_model: CostModel = field(default_factory=CostModel.research)
    research_only: bool = field(default=True, init=False)
    live_orders: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        capital = _number(self.capital_usd, "capital_usd", positive=True)
        minimum = _number(self.min_profit_usd, "min_profit_usd", positive=True)
        preferred = _number(
            self.preferred_profit_usd, "preferred_profit_usd", positive=True
        )
        if preferred < minimum:
            raise ValueError("preferred_profit_usd must be >= min_profit_usd")
        if not isinstance(self.cost_model, CostModel):
            raise TypeError("cost_model must be a CostModel")
        object.__setattr__(self, "capital_usd", capital)
        object.__setattr__(self, "min_profit_usd", minimum)
        object.__setattr__(self, "preferred_profit_usd", preferred)
