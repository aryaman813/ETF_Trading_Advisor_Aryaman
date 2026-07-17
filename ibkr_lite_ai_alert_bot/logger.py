import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from schemas import MarketSnapshot, TradeProposal, RiskDecision


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

JSONL_PATH = LOG_DIR / "events.jsonl"
CSV_PATH = LOG_DIR / "signals.csv"


def log_event(event_type: str, payload: dict) -> None:
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def log_signal(snapshot: MarketSnapshot, proposal: TradeProposal, decision: RiskDecision) -> None:
    fieldnames = [
        "timestamp_utc",
        "symbol",
        "last_close",
        "action",
        "quantity",
        "order_type",
        "limit_price",
        "confidence",
        "approved",
        "risk_reason",
        "estimated_notional",
        "rationale",
        "invalidation_condition",
    ]

    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": proposal.symbol,
        "last_close": snapshot.last_close,
        "action": proposal.action,
        "quantity": proposal.quantity,
        "order_type": proposal.order_type,
        "limit_price": proposal.limit_price,
        "confidence": proposal.confidence,
        "approved": decision.approved,
        "risk_reason": decision.reason,
        "estimated_notional": decision.estimated_notional,
        "rationale": proposal.rationale,
        "invalidation_condition": proposal.invalidation_condition,
    }

    file_exists = CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
