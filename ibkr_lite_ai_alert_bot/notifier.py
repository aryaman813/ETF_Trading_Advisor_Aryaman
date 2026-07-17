import requests
from schemas import TradeProposal, MarketSnapshot, RiskDecision


def format_alert(snapshot: MarketSnapshot, proposal: TradeProposal, decision: RiskDecision) -> str:
    status = "APPROVED FOR MANUAL REVIEW" if decision.approved else "REJECTED / HOLD"

    return f"""
AI Trading Alert — {status}

Symbol: {proposal.symbol}
Action: {proposal.action}
Quantity: {proposal.quantity:.4f} shares
Order Type: {proposal.order_type}
Limit Price: {proposal.limit_price}
Last Close: {snapshot.last_close:.2f}
Estimated Notional: {decision.estimated_notional}
Approx Trade Value: ${proposal.quantity * proposal.limit_price if proposal.limit_price else 0:.2f}

Confidence: {proposal.confidence:.2f}
Risk Decision: {decision.reason}

Rationale:
{proposal.rationale}

Invalidation:
{proposal.invalidation_condition}

Manual Action:
{proposal.suggested_manual_action}

Reminder: This app does not execute trades. If you agree, place the order manually in IBKR Lite.
""".strip()


def send_telegram_alert(bot_token: str | None, chat_id: str | None, message: str) -> bool:
    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    response.raise_for_status()
    return True
