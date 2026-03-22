#!/usr/bin/env python3
"""Ingest OHLCV daily data from Alpha Vantage into MySQL.

Docs: https://www.alphavantage.co/documentation/

Env:
    ALPHAVANTAGE_API_KEY=...

Examples:
    python .\scripts\ingest_alphavantage.py --symbol AAPL --years 10 --outputsize full
    python .\scripts\ingest_alphavantage.py --symbol AAPL --outputsize compact

Notes:
- outputsize=full requires a premium API key for TIME_SERIES_DAILY.
- Free keys may be limited to a small number of requests per day.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from sqlalchemy.dialects.mysql import insert as mysql_insert

from btweb.db import SessionLocal, engine
from btweb.models import Base, OhlcvDaily


ALPHAVANTAGE_QUERY_URL = "https://www.alphavantage.co/query"


def _years_ago(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, day=28)


def _fetch_json(params: dict[str, str], *, timeout_sec: int = 30) -> dict:
    url = f"{ALPHAVANTAGE_QUERY_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "btweb/1.0"})
    with urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read()

    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        preview = raw[:200].decode("utf-8", errors="replace")
        raise RuntimeError(f"failed to parse JSON: {exc}; preview={preview!r}")


def _pick_time_series_key(data: dict) -> str:
    for k in data.keys():
        if isinstance(k, str) and "Time Series" in k:
            return k
    raise KeyError("missing time series in response")


def _parse_ohlcv_rows(
    data: dict,
    *,
    symbol: str,
    start: date,
    end: date,
) -> list[dict]:
    ts_key = _pick_time_series_key(data)
    ts = data.get(ts_key)
    if not isinstance(ts, dict) or not ts:
        return []

    rows: list[dict] = []
    for day_str, bar in ts.items():
        if not isinstance(day_str, str) or not isinstance(bar, dict):
            continue
        try:
            d = date.fromisoformat(day_str)
        except ValueError:
            continue
        if d < start or d > end:
            continue

        open_s = bar.get("1. open")
        high_s = bar.get("2. high")
        low_s = bar.get("3. low")
        close_s = bar.get("4. close")

        vol_s = bar.get("5. volume")
        adj_close_s = bar.get("5. adjusted close")
        if vol_s is None and "6. volume" in bar:
            vol_s = bar.get("6. volume")

        if open_s is None or high_s is None or low_s is None or close_s is None:
            continue

        volume: int | None = None
        if vol_s is not None:
            try:
                volume = int(float(str(vol_s)))
            except Exception:
                volume = None

        adj_close: float | None = None
        if adj_close_s is not None:
            try:
                adj_close = float(str(adj_close_s))
            except Exception:
                adj_close = None

        rows.append(
            {
                "symbol": symbol,
                "trade_date": d,
                "open": float(str(open_s)),
                "high": float(str(high_s)),
                "low": float(str(low_s)),
                "close": float(str(close_s)),
                "volume": volume,
                "adj_close": adj_close,
            }
        )

    rows.sort(key=lambda r: r["trade_date"])
    return rows


def _chunked(rows: list[dict], size: int):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="AAPL", help="Ticker symbol, e.g. AAPL")
    parser.add_argument(
        "--function",
        default="TIME_SERIES_DAILY",
        choices=["TIME_SERIES_DAILY", "TIME_SERIES_DAILY_ADJUSTED"],
        help="Alpha Vantage function",
    )
    parser.add_argument(
        "--outputsize",
        default=None,
        choices=["compact", "full"],
        help="compact=latest 100 points; full=20+ years (premium for some endpoints)",
    )
    parser.add_argument("--years", type=int, default=10, help="How many years back from end date")
    parser.add_argument("--start", type=date.fromisoformat, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=date.fromisoformat, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--chunk", type=int, default=500, help="Upsert batch size")
    args = parser.parse_args()

    symbol = str(args.symbol).strip().upper()
    if not symbol:
        raise SystemExit("symbol is required")

    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing ALPHAVANTAGE_API_KEY. Put it in .env or set env var ALPHAVANTAGE_API_KEY."
        )

    end = args.end or date.today()
    start = args.start or _years_ago(end, int(args.years))
    if start > end:
        raise SystemExit("start must be <= end")

    outputsize = args.outputsize
    if not outputsize:
        outputsize = "full" if int(args.years) > 1 else "compact"

    params = {
        "function": args.function,
        "symbol": symbol,
        "apikey": api_key,
        "datatype": "json",
        "outputsize": outputsize,
    }

    print(f"Requesting Alpha Vantage: {args.function} {symbol} outputsize={outputsize} ...")
    data = _fetch_json(params)

    for key in ("Error Message", "Information", "Note"):
        if key in data and isinstance(data.get(key), str):
            raise SystemExit(f"Alpha Vantage error: {data[key]}")

    rows = _parse_ohlcv_rows(data, symbol=symbol, start=start, end=end)
    if not rows:
        raise SystemExit(
            "No rows parsed. If you are using a free API key, outputsize=full may be unavailable; try --outputsize compact."
        )

    Base.metadata.create_all(bind=engine)

    inserted = 0
    with SessionLocal() as session:
        for batch in _chunked(rows, int(args.chunk)):
            stmt = mysql_insert(OhlcvDaily).values(batch)
            stmt = stmt.on_duplicate_key_update(
                open=stmt.inserted.open,
                high=stmt.inserted.high,
                low=stmt.inserted.low,
                close=stmt.inserted.close,
                volume=stmt.inserted.volume,
                adj_close=stmt.inserted.adj_close,
            )
            session.execute(stmt)
            session.commit()
            inserted += len(batch)
            print(f"Upserted {inserted}/{len(rows)} rows ...")

    print("OK")


if __name__ == "__main__":
    main()