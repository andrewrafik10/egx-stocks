"""Weekly top-10 equal-weight portfolio backtest for EGX signal snapshots.

Input: data/history.csv with one row per ticker and as_of_date.
Strategy: rank by opportunity_score, hold top N equally weighted until the
next signal date, then rebalance. Estimated one-way transaction cost is
charged on portfolio turnover. This is a research approximation, not an
execution-grade backtest: price timestamps, dividends, corporate actions,
liquidity, suspensions, and next-session entry must be validated separately.

Optional benchmark input: data/egx100_history.csv with columns as_of_date, close.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Optional

DEFAULT_HISTORY = "data/history.csv"
DEFAULT_BENCHMARK = "data/egx100_history.csv"
DEFAULT_OUTDIR = "output/backtest"
TOP_N = 10
COST_BPS_PER_SIDE = 25.0  # analyst assumption; replace with actual fees/slippage
MIN_SIGNAL_DATES_FOR_ANNUAL_CLAIM = 40


def number(value: str) -> Optional[float]:
    try:
        if value is None or str(value).strip() == "":
            return None
        x = float(value)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def read_history(path: str):
    grouped = defaultdict(list)
    with Path(path).open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                d = date.fromisoformat(row["as_of_date"])
            except (KeyError, ValueError):
                continue
            price = number(row.get("price", ""))
            score = number(row.get("opportunity_score", ""))
            if price is None or price <= 0 or score is None:
                continue
            row["_date"] = d
            row["_price"] = price
            row["_score"] = score
            grouped[d].append(row)
    return {d: sorted(rows, key=lambda r: (-r["_score"], r["ticker"]))
            for d, rows in sorted(grouped.items())}


def read_benchmark(path: str):
    p = Path(path)
    if not p.exists():
        return {}
    result = {}
    with p.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                d = date.fromisoformat(row["as_of_date"])
            except (KeyError, ValueError):
                continue
            close = number(row.get("close", ""))
            if close and close > 0:
                result[d] = close
    return dict(sorted(result.items()))


def calc_drawdown(equity_values):
    peak = 1.0
    worst = 0.0
    for value in equity_values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return worst


def run(history_path=DEFAULT_HISTORY, benchmark_path=DEFAULT_BENCHMARK,
        outdir=DEFAULT_OUTDIR, top_n=TOP_N, cost_bps=COST_BPS_PER_SIDE):
    dates = read_history(history_path)
    all_dates = list(dates)
    if len(all_dates) < 2:
        raise ValueError("Need at least two dated signal snapshots with prices and scores.")

    benchmark = read_benchmark(benchmark_path)
    output = Path(outdir)
    output.mkdir(parents=True, exist_ok=True)

    equity = 1.0
    previous_weights = {}
    portfolio_rows = []
    holdings_rows = []
    returns = []
    cumulative = []
    turnover_total = 0.0
    cost_rate = cost_bps / 10000.0

    for idx, signal_date in enumerate(all_dates[:-1]):
        next_date = all_dates[idx + 1]
        selected = dates[signal_date][:top_n]
        if not selected:
            continue
        target_weights = {r["ticker"]: 1.0 / len(selected) for r in selected}

        # Turnover is half the sum of absolute changes in portfolio weights,
        # including names sold and names bought. Initial deployment is turnover 1.
        names = set(previous_weights) | set(target_weights)
        turnover = 0.5 * sum(abs(target_weights.get(t, 0.0) -
                                 previous_weights.get(t, 0.0)) for t in names)
        if not previous_weights:
            turnover = 1.0
        transaction_cost = turnover * cost_rate

        next_prices = {r["ticker"]: r["_price"] for r in dates[next_date]}
        weighted_return = 0.0
        actual_weight = 0.0
        for row in selected:
            ticker = row["ticker"]
            exit_price = next_prices.get(ticker)
            stock_return = exit_price / row["_price"] - 1 if exit_price else None
            weight = target_weights[ticker]
            holdings_rows.append({
                "signal_date": signal_date.isoformat(),
                "next_snapshot_date": next_date.isoformat(),
                "ticker": ticker,
                "opportunity_score": row["_score"],
                "entry_price": row["_price"],
                "exit_price": exit_price if exit_price is not None else "",
                "stock_return": stock_return if stock_return is not None else "",
                "target_weight": weight,
            })
            if stock_return is not None:
                weighted_return += weight * stock_return
                actual_weight += weight

        # Do not silently treat missing holdings as cash: normalize the observed
        # portion and flag coverage. This is descriptive, not a tradable result.
        gross_return = weighted_return / actual_weight if actual_weight else 0.0
        net_return = (1.0 + gross_return) * (1.0 - transaction_cost) - 1.0
        equity *= (1.0 + net_return)
        returns.append(net_return)
        cumulative.append(equity)
        turnover_total += turnover

        bench_return = ""
        if benchmark:
            start_bench = next((v for d, v in benchmark.items() if d >= signal_date), None)
            end_bench = next((v for d, v in benchmark.items() if d >= next_date), None)
            if start_bench and end_bench:
                bench_return = end_bench / start_bench - 1

        portfolio_rows.append({
            "signal_date": signal_date.isoformat(),
            "next_snapshot_date": next_date.isoformat(),
            "holdings_count": len(selected),
            "price_coverage_pct": round(actual_weight * 100, 2),
            "gross_portfolio_return": gross_return,
            "turnover": turnover,
            "estimated_transaction_cost_pct": transaction_cost * 100,
            "net_portfolio_return": net_return,
            "cumulative_equity": equity,
            "benchmark_return": bench_return,
        })
        previous_weights = target_weights

    total_return = equity - 1.0
    n = len(returns)
    positive_rate = sum(r > 0 for r in returns) / n if n else None
    # Annualized metrics are intentionally omitted for sparse/irregular snapshots.
    days = (all_dates[-1] - all_dates[0]).days
    enough_dates = len(all_dates) >= MIN_SIGNAL_DATES_FOR_ANNUAL_CLAIM and days >= 300
    summary = {
        "strategy": f"Top {top_n} opportunity scores, equal-weight, rebalance each signal snapshot",
        "history_file": history_path,
        "first_signal_date": all_dates[0].isoformat(),
        "last_signal_date": all_dates[-1].isoformat(),
        "signal_dates": len(all_dates),
        "calendar_days_covered": days,
        "periods_evaluated": n,
        "cost_bps_per_side_assumption": cost_bps,
        "total_return_net": total_return,
        "period_win_rate": positive_rate,
        "max_drawdown_observed": calc_drawdown([1.0] + cumulative),
        "benchmark_available": bool(benchmark),
        "annual_backtest_evidence_sufficient": enough_dates,
        "warning": None if enough_dates else (
            "Insufficient history for a one-year conclusion. Need at least "
            f"{MIN_SIGNAL_DATES_FOR_ANNUAL_CLAIM} dated signal snapshots spanning 300+ days. "
            "Current results are exploratory only."
        ),
    }

    def write_csv(filename, rows):
        if not rows:
            return
        with (output / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    write_csv("portfolio_periods.csv", portfolio_rows)
    write_csv("portfolio_holdings.csv", holdings_rows)
    (output / "portfolio_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary, portfolio_rows, holdings_rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", default=DEFAULT_HISTORY)
    parser.add_argument("--benchmark", default=DEFAULT_BENCHMARK)
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    parser.add_argument("--top-n", type=int, default=TOP_N)
    parser.add_argument("--cost-bps", type=float, default=COST_BPS_PER_SIDE)
    args = parser.parse_args()
    summary, _, _ = run(args.history, args.benchmark, args.outdir,
                        args.top_n, args.cost_bps)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
