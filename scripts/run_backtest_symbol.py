#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from btweb.backtest import run_backtest
from btweb.strategy_loader import load_strategy_class


def configure_runtime() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    cache_dir = Path(__file__).resolve().parent.parent / ".cache" / "yfinance"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YFINANCE_CACHE_DIR", str(cache_dir))
    try:
        yf.set_tz_cache_location(str(cache_dir))
    except Exception:
        pass


def years_ago(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, day=28)


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if "Close" not in df.columns:
        return pd.DataFrame()

    out = df.copy().rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    needed = ["open", "high", "low", "close", "volume"]
    if not all(c in out.columns for c in needed):
        return pd.DataFrame()

    out = out[needed].dropna(subset=["open", "high", "low", "close"])
    out["openinterest"] = 0
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out.sort_index()


def fetch_yfinance_data(symbol: str, start: date, end: date, retries: int, sleep_sec: float) -> pd.DataFrame:
    last_exc: Exception | None = None
    end_exclusive = end + timedelta(days=1)

    for i in range(1, retries + 1):
        try:
            df = yf.download(
                symbol,
                start=start.isoformat(),
                end=end_exclusive.isoformat(),
                interval="1d",
                auto_adjust=False,
                progress=False,
                actions=False,
                threads=True,
                timeout=20,
            )
            normalized = normalize_ohlcv(df)
            if not normalized.empty:
                return normalized
        except Exception as exc:  # noqa: BLE001
            last_exc = exc

        try:
            ticker = yf.Ticker(symbol)
            df2 = ticker.history(
                start=start.isoformat(),
                end=end_exclusive.isoformat(),
                interval="1d",
                auto_adjust=False,
                actions=False,
            )
            normalized2 = normalize_ohlcv(df2)
            if not normalized2.empty:
                return normalized2
        except Exception as exc:  # noqa: BLE001
            last_exc = exc

        if i < retries:
            time.sleep(sleep_sec * i)

    if last_exc:
        raise RuntimeError(f"yfinance failed for {symbol}: {last_exc}")
    raise RuntimeError(f"yfinance failed for {symbol}: empty data")


def fetch_alphavantage_data(symbol: str, start: date, end: date) -> pd.DataFrame:
    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
    if not api_key:
        return pd.DataFrame()

    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "full",
        "datatype": "json",
        "apikey": api_key,
    }
    url = "https://www.alphavantage.co/query?" + urlencode(params)
    req = Request(url, headers={"User-Agent": "btweb/1.0"})
    with urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    for k in ("Error Message", "Information", "Note"):
        if k in payload:
            raise RuntimeError(f"alphavantage failed: {payload[k]}")

    ts = payload.get("Time Series (Daily)")
    if not isinstance(ts, dict) or not ts:
        return pd.DataFrame()

    rows: list[dict] = []
    for day_str, bar in ts.items():
        d = date.fromisoformat(day_str)
        if d < start or d > end:
            continue
        rows.append(
            {
                "datetime": pd.Timestamp(day_str),
                "open": float(bar["1. open"]),
                "high": float(bar["2. high"]),
                "low": float(bar["3. low"]),
                "close": float(bar["4. close"]),
                "volume": float(bar.get("6. volume", bar.get("5. volume", 0))),
                "openinterest": 0,
            }
        )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).set_index("datetime").sort_index()


def fetch_data(symbol: str, start: date, end: date, retries: int, sleep_sec: float) -> tuple[pd.DataFrame, str]:
    try:
        return fetch_yfinance_data(symbol, start, end, retries, sleep_sec), "yfinance"
    except Exception as yf_exc:  # noqa: BLE001
        print(f"yfinance fallback triggered: {yf_exc}")

    av = fetch_alphavantage_data(symbol, start, end)
    if not av.empty:
        return av, "alphavantage"

    raise RuntimeError(f"failed to fetch market data for {symbol} from both yfinance and alphavantage")


def to_records_by_date(rows: list[dict], date_key: str = "date") -> list[dict]:
    return sorted(rows, key=lambda x: str(x.get(date_key, "")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Backtrader backtest for a symbol")
    parser.add_argument("--symbol", default="PG", help="Ticker, e.g. PG")
    parser.add_argument("--strategy-id", default="pg_trend_breakout_atr.py", help="File under strategies/")
    parser.add_argument("--cash", type=float, default=100000.0)
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--start", type=date.fromisoformat, default=None)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--sleep-sec", type=float, default=2.0)
    parser.add_argument("--out-dir", default="backtest_outputs")
    args = parser.parse_args()

    configure_runtime()

    symbol = args.symbol.strip().upper()
    end = args.end or date.today()
    start = args.start or years_ago(end, args.years)

    strategy_dir = Path(__file__).resolve().parent.parent / "strategies"
    strategy_cls = load_strategy_class(strategy_dir, args.strategy_id)

    print(f"[1/3] Fetching {symbol} daily data: {start} -> {end}")
    data, data_source = fetch_data(symbol, start, end, retries=args.retries, sleep_sec=args.sleep_sec)
    if data.empty:
        raise SystemExit("No market data downloaded.")

    print(f"[2/3] Running backtest with strategy: {strategy_cls.__name__}")
    result = run_backtest(
        strategy_cls=strategy_cls,
        data=data,
        symbol=symbol,
        cash=float(args.cash),
        start_date=start,
        end_date=end,
        commission=float(args.commission),
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = f"{symbol}_{strategy_cls.__name__}_{start.isoformat()}_{end.isoformat()}"
    metrics_path = out_dir / f"{stamp}_metrics.json"
    trades_path = out_dir / f"{stamp}_trades.csv"
    equity_path = out_dir / f"{stamp}_equity.csv"

    trades = to_records_by_date([*result.buys, *result.sells])
    pd.DataFrame(trades).to_csv(trades_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(result.equity).to_csv(equity_path, index=False, encoding="utf-8-sig")

    metrics = dict(result.metrics)
    metrics["data_source"] = data_source
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[3/3] Done")
    print("--- Metrics ---")
    for k in [
        "symbol",
        "strategy",
        "data_source",
        "start_date",
        "end_date",
        "start_cash",
        "end_value",
        "pnl",
        "return_pct",
        "annual_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "sortino",
        "calmar",
        "win_rate_pct",
        "avg_win_loss_ratio",
        "trade_count",
    ]:
        print(f"{k}: {metrics.get(k)}")

    print(f"metrics: {metrics_path}")
    print(f"trades : {trades_path}")
    print(f"equity : {equity_path}")


if __name__ == "__main__":
    main()