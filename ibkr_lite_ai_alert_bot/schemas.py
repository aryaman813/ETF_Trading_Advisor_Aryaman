from typing import Literal
from pydantic import BaseModel, Field


class MarketSnapshot(BaseModel):
    symbol: str
    last_close: float
    sma_20: float | None
    sma_50: float | None
    rsi_14: float | None
    average_volume_20: float | None
    latest_volume: float | None
    pct_change_1d: float | None
    pct_change_5d: float | None


class TradeProposal(BaseModel):
    action: Literal["BUY", "SELL", "HOLD"]
    symbol: str
    asset_type: Literal["STK"] = "STK"

    # Was int. Now float so it can be 0.01, 0.05, 0.25, etc.
    quantity: float = Field(ge=0, le=100)

    order_type: Literal["LMT"] = "LMT"
    limit_price: float | None = Field(default=None, gt=0)
    time_in_force: Literal["DAY"] = "DAY"
    confidence: float = Field(ge=0, le=1)
    rationale: str
    invalidation_condition: str
    suggested_manual_action: str


class RiskDecision(BaseModel):
    approved: bool
    reason: str
    estimated_notional: float | None = None
