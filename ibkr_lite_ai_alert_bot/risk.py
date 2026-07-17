from schemas import TradeProposal, MarketSnapshot, RiskDecision
import math

ALLOWED_SYMBOLS = {
    "SPY", "QQQ", "XLK", "XLF", "XLY",
    "AAPL", "MSFT", "NVDA",
    "WMT", "HD", "TGT"
}

MAX_NOTIONAL_USD = 5.00
MIN_NOTIONAL_USD = 1.00
MAX_QUANTITY = 1.0
MIN_QUANTITY = 0.0001
MIN_CONFIDENCE = 0.85
MAX_LIMIT_DISTANCE_PCT = 0.75

def round_down_quantity(quantity: float, decimals: int = 4) -> float:
    factor = 10 ** decimals
    return math.floor(quantity * factor) / factor


def suggested_fractional_quantity(limit_price: float, target_notional: float = 5.00) -> float:
    if limit_price <= 0:
        return 0.0

    raw_quantity = target_notional / limit_price
    return round_down_quantity(raw_quantity, 4)

def validate_proposal(proposal: TradeProposal, snapshot: MarketSnapshot) -> RiskDecision:
    if proposal.action == "HOLD":
        return RiskDecision(approved=False, reason="Model chose HOLD.", estimated_notional=0)

    if proposal.symbol.upper() not in ALLOWED_SYMBOLS:
        return RiskDecision(approved=False, reason=f"{proposal.symbol} is not in the allowlist.")

    if proposal.asset_type != "STK":
        return RiskDecision(approved=False, reason="Only stocks are allowed.")

    if proposal.order_type != "LMT":
        return RiskDecision(approved=False, reason="Only limit orders are allowed.")

    if proposal.quantity <= 0:
        return RiskDecision(approved=False, reason="Quantity must be positive for BUY/SELL.")

    if proposal.quantity < MIN_QUANTITY:
        return RiskDecision(
            approved=False,
            reason=f"Quantity is below minimum fractional size of {MIN_QUANTITY}."
        )

    if proposal.quantity > MAX_QUANTITY:
        return RiskDecision(
            approved=False,
            reason=f"Quantity exceeds max of {MAX_QUANTITY} share."
        )

    if proposal.confidence < MIN_CONFIDENCE:
        return RiskDecision(
            approved=False,
            reason=f"Confidence below {MIN_CONFIDENCE}."
        )

    if proposal.limit_price is None:
        return RiskDecision(approved=False, reason="Limit price is required.")

    distance_pct = abs(proposal.limit_price / snapshot.last_close - 1) * 100
    if distance_pct > MAX_LIMIT_DISTANCE_PCT:
        return RiskDecision(
            approved=False,
            reason=(
                f"Limit price is {distance_pct:.2f}% away from last close; "
                f"max is {MAX_LIMIT_DISTANCE_PCT:.2f}%."
            ),
        )

    notional = proposal.quantity * proposal.limit_price

    if notional < MIN_NOTIONAL_USD:
        return RiskDecision(
            approved=False,
            reason=f"Notional ${notional:.2f} is below minimum ${MIN_NOTIONAL_USD:.2f}.",
            estimated_notional=notional,
        )

    if notional > MAX_NOTIONAL_USD:
        return RiskDecision(
            approved=False,
            reason=f"Notional ${notional:.2f} exceeds max ${MAX_NOTIONAL_USD:.2f}.",
            estimated_notional=notional,
        )

    return RiskDecision(
        approved=True,
        reason="Passed fractional-share risk checks.",
        estimated_notional=notional,
    )
