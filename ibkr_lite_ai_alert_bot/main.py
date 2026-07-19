import argparse
from datetime import date
from config import get_config
from backtest import BacktestConfig, load_backtest_universe, run_etf_backtest
from market_data import get_snapshot
from llm import ProposalEngine
from risk import validate_proposal
from notifier import format_alert, send_telegram_alert
from logger import log_event, log_signal
from performance import build_evaluation_summary, evaluate_signals
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


def run_evaluation(days_forward: int, cost_bps: float) -> None:
    df = evaluate_signals(days_forward=days_forward)
    if df.empty:
        print("No completed actionable signals to evaluate yet.")
        return

    print(df.to_string(index=False))
    print()
    summary = build_evaluation_summary(df, days_forward=days_forward, cost_bps=cost_bps)

    print("Summary:")
    print(f"Universe: {', '.join(summary['universe'])}")
    print(f"Watchlist: {', '.join(summary['watchlist'])}")
    print(
        f"Testing period: {summary['testing_period']['start']} to {summary['testing_period']['end']} "
        f"(forward horizon: {summary['testing_period']['forward_days']} trading days)"
    )
    print(f"Signal definition: {summary['signal_definition']}")
    print(f"Signals evaluated: {summary['n_signals']}")
    print(f"Hit rate: {summary['hit_rate_pct']:.2f}%")
    print(f"Average gross return: {summary['avg_gross_return_pct']:.2f}%")
    print(f"Average return after costs: {summary['avg_net_return_pct_after_costs']:.2f}%")
    print(f"Median return after costs: {summary['median_net_return_pct_after_costs']:.2f}%")
    print(f"Gross Sharpe ratio: {summary['gross_sharpe_ratio']}")
    print(f"Net Sharpe ratio: {summary['net_sharpe_ratio']}")
    print(f"Confidence IC: {summary['confidence_ic']}")
    print(f"Max drawdown after costs: {summary['max_drawdown_pct_after_costs']:.2f}%")
    print(f"Cumulative return after costs: {summary['cumulative_return_pct_after_costs']:.2f}%")
    print(f"Cost assumption: {summary['cost_bps_round_trip']:.1f} bps round trip")


def run_backtest(start_date: str, end_date: str, universe_raw: str | None, hold_days: int, cost_bps: float) -> None:
    universe = load_backtest_universe(universe_raw)
    cfg = BacktestConfig(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        hold_days=hold_days,
        cost_bps_round_trip=cost_bps,
    )
    summary = run_etf_backtest(cfg)

    print("Backtest Summary:")
    print(f"Universe: {', '.join(summary['universe'])}")
    print(
        f"Testing period: {summary['testing_period']['start']} to {summary['testing_period']['end']} "
        f"(hold period: {summary['testing_period']['hold_days']} trading days)"
    )
    print(f"Signal definition: {summary['signal_definition']}")
    print(f"Trades: {summary['n_trades']}")
    print(f"Hit rate: {summary['hit_rate_pct']:.2f}%")
    print(f"Average gross trade return: {summary['avg_gross_return_pct']:.2f}%")
    print(f"Average net trade return: {summary['avg_net_return_pct']:.2f}%")
    print(f"Gross Sharpe ratio: {summary['gross_sharpe_ratio']}")
    print(f"Net Sharpe ratio: {summary['net_sharpe_ratio']}")
    print(f"IC between signal score and net return: {summary['confidence_ic']}")
    print(f"Max drawdown: {summary['max_drawdown_pct']:.2f}%")
    print(f"Cumulative strategy return: {summary['cumulative_return_pct']:.2f}%")
    print(f"Buy-and-hold return: {summary['buy_and_hold_return_pct']:.2f}%")
    print(f"Equal-weight benchmark return: {summary['equal_weight_return_pct']:.2f}%")
    print(f"Equal-weight benchmark Sharpe: {summary['equal_weight_sharpe_ratio']}")
    print(f"Equal-weight benchmark max drawdown: {summary['equal_weight_max_drawdown_pct']:.2f}%")
    print(f"Cost assumption: {summary['cost_bps_round_trip']:.1f} bps round trip")
    if summary.get("plot_files"):
        print("Plots:")
        for plot_file in summary["plot_files"]:
            print(f"- {plot_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="IBKR Lite AI alert-only trading assistant")
    parser.add_argument("--scan", action="store_true", help="Scan watchlist and generate alerts")
    parser.add_argument("--evaluate", type=int, metavar="DAYS", help="Evaluate signals after N trading days")
    parser.add_argument("--backtest", action="store_true", help="Run the ETF strategy backtest")
    parser.add_argument("--start", default="2023-01-01", help="Backtest start date in YYYY-MM-DD format")
    parser.add_argument("--end", default=date.today().isoformat(), help="Backtest end date in YYYY-MM-DD format")
    parser.add_argument("--universe", default=None, help="Comma-separated ETF universe for backtesting")
    parser.add_argument("--hold-days", type=int, default=5, help="Hold period for the backtest strategy")
    parser.add_argument(
        "--cost-bps",
        type=float,
        default=10.0,
        metavar="BPS",
        help="Round-trip cost in basis points to subtract from each trade",
    )

    args = parser.parse_args()

    if args.scan:
        run_scan()
    elif args.evaluate:
        run_evaluation(days_forward=args.evaluate, cost_bps=args.cost_bps)
    elif args.backtest:
        run_backtest(
            start_date=args.start,
            end_date=args.end,
            universe_raw=args.universe,
            hold_days=args.hold_days,
            cost_bps=args.cost_bps,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
