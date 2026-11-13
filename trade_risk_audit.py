"""Offline pre-trade risk audit. No orders, forecasts or live-price assumptions."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Trade:
    ticker: str
    entry: float
    quantity: int
    stop: float
    equity: float
    risk_budget_pct: float = 1.0


def audit(trade: Trade, *, quote_timestamp: Optional[str] = None) -> dict:
    if not (trade.entry > 0 and trade.stop > 0 and trade.equity > 0):
        raise ValueError("Prices and equity must be positive")
    if trade.quantity <= 0 or not isinstance(trade.quantity, int):
        raise ValueError("Quantity must be a positive integer")
    if not (0 < trade.risk_budget_pct <= 100):
        raise ValueError("Risk budget percentage out of range")
    if trade.stop >= trade.entry:
        raise ValueError("Long-position stop must be below entry")
    if quote_timestamp is not None:
        datetime.fromisoformat(quote_timestamp)
    loss = (trade.entry - trade.stop) * trade.quantity
    budget = trade.equity * trade.risk_budget_pct / 100
    return {
        "ticker": trade.ticker,
        "notional_cny": round(trade.entry * trade.quantity, 2),
        "stop_loss_cny_before_costs_slippage": round(loss, 2),
        "risk_budget_cny": round(budget, 2),
        "exceeds_risk_budget": loss > budget,
        "max_shares_at_budget": max(0, int(budget // (trade.entry - trade.stop))),
        "quote_timestamp_verified": False,
        "warning": "Stop is not guaranteed execution price; gaps, liquidity and fees may increase loss. No real-time quote verification.",
    }


if __name__ == "__main__":
    from pprint import pprint
    pprint(audit(Trade("688777", 64.37, 1437, 64.37 * .95, 300000)))
