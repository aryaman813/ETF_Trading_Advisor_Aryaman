import json
from google import genai
from google.genai import types

from schemas import MarketSnapshot, TradeProposal


TRADE_PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
        "symbol": {"type": "string"},
        "asset_type": {"type": "string", "enum": ["STK"]},
        "quantity": {
            "type": "number",
            "minimum": 0,
            "maximum": 100
        },
        "order_type": {"type": "string", "enum": ["LMT"]},
        "limit_price": {"type": ["number", "null"]},
        "time_in_force": {"type": "string", "enum": ["DAY"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
        "invalidation_condition": {"type": "string"},
        "suggested_manual_action": {"type": "string"},
    },
    "required": [
        "action",
        "symbol",
        "asset_type",
        "quantity",
        "order_type",
        "limit_price",
        "time_in_force",
        "confidence",
        "rationale",
        "invalidation_condition",
        "suggested_manual_action",
    ],
    "additionalProperties": False,
}


class ProposalEngine:
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def propose(self, snapshot: MarketSnapshot) -> TradeProposal:
        prompt = {
            "market_snapshot": snapshot.model_dump(),
            "instructions": [
                "This is an alert-only assistant for manual execution in IBKR Lite.",
                "Do not claim that any trade is guaranteed profitable.",
                "Prefer HOLD unless the setup is strong and explainable.",
                "Use only stock limit orders.",
                "Quantity may be fractional, e.g. 0.01, 0.05, 0.1, 0.25.",
                "Use 0 for HOLD.",
                "Target a trade value between $1 and $10 because the account size is only $50.",
                "Calculate quantity approximately as target_dollar_amount / limit_price.",
                "Round quantity down to 4 decimal places.",
                "For BUY, set limit_price at or below last_close.",
                "For SELL, set limit_price at or above last_close.",
                "Never suggest options, futures, margin, leverage, short selling, or market orders.",
            ],
            "required_json_shape": {
                "action": "BUY | SELL | HOLD",
                "symbol": "ticker symbol",
                "asset_type": "STK",
                "quantity": "number, fractional allowed",
                "order_type": "LMT",
                "limit_price": "number or null",
                "time_in_force": "DAY",
                "confidence": "number from 0 to 1",
                "rationale": "string",
                "invalidation_condition": "string",
                "suggested_manual_action": "string",
            },
        }

        response = self.client.models.generate_content(
            model=self.model,
            contents=json.dumps(prompt),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        return TradeProposal.model_validate_json(response.text)
