import argparse
from config import get_config
from market_data import get_snapshot
from llm import ProposalEngine
from risk import validate_proposal
from notifier import format_alert, send_telegram_alert
from logger import log_event, log_signal
from performance import evaluate_signals
from risk import suggested_fractional_quantity
import time

def propose_with_retries(engine, snapshot, max_attempts: int = 3):
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            return engine.propose(snapshot)
        except Exception as exc:
            last_error = exc
            message = str(exc)

            retryable = (
                "500" in message
                or "503" in message
                or "INTERNAL" in message
                or "UNAVAILABLE" in message
                or "RESOURCE_EXHAUSTED" in message
            )

            if not retryable or attempt == max_attempts:
                raise

            wait_seconds = 3 * attempt
            print(
                f"LLM error on {snapshot.symbol}; retrying in "
                f"{wait_seconds}s... attempt {attempt}/{max_attempts}"
            )
            time.sleep(wait_seconds)

    raise last_error

def run_scan() -> None:
    cfg = get_config()
    engine = ProposalEngine(api_key=cfg.gemini_api_key, model=cfg.model)

    print(f"Scanning watchlist: {', '.join(cfg.watchlist)}")

    for symbol in cfg.watchlist:
        try:
            snapshot = get_snapshot(symbol)
            proposal = propose_with_retries(engine, snapshot)
            if proposal.action in {"BUY", "SELL"} and proposal.limit_price:
                proposal.quantity = suggested_fractional_quantity(
                limit_price=proposal.limit_price,
                target_notional=2.00,
                )
            decision = validate_proposal(proposal, snapshot)
            alert = format_alert(snapshot, proposal, decision)

            print("\n" + "=" * 80)
            print(alert)

            sent = send_telegram_alert(cfg.telegram_bot_token, cfg.telegram_chat_id, alert)
            if sent:
                print("Telegram alert sent.")

            log_signal(snapshot, proposal, decision)
            log_event("scan_success", {
                "snapshot": snapshot.model_dump(),
                "proposal": proposal.model_dump(),
                "decision": decision.model_dump(),
                "telegram_sent": sent,
            })

        except Exception as exc:
            print(f"Error scanning {symbol}: {exc}")
            log_event("scan_error", {"symbol": symbol, "error": str(exc)})


def run_evaluation(days_forward: int) -> None:
    df = evaluate_signals(days_forward=days_forward)
    if df.empty:
        print("No completed actionable signals to evaluate yet.")
        return

    print(df.to_string(index=False))
    print()
    print("Summary:")
    print(df.describe(include="all").to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="IBKR Lite AI alert-only trading assistant")
    parser.add_argument("--scan", action="store_true", help="Scan watchlist and generate alerts")
    parser.add_argument("--evaluate", type=int, metavar="DAYS", help="Evaluate signals after N trading days")

    args = parser.parse_args()

    if args.scan:
        run_scan()
    elif args.evaluate:
        run_evaluation(days_forward=args.evaluate)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
