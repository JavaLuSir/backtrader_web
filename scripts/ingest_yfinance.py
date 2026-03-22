#!/usr/bin/env python3
"""Ingest OHLCV daily data from yfinance into MySQL.

Example:
    python .\scripts\ingest_yfinance.py --symbol AAPL --years 10

It writes into table: ohlcv_daily (symbol, trade_date, open, high, low, close, volume, adj_close)
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.mysql import insert as mysql_insert

from btweb.db import SessionLocal, engine
from btweb.models import Base, OhlcvDaily


def _years_ago(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        # e.g. Feb 29
        return d.replace(year=d.year - years, day=28)


def _download_daily(symbol: str, start: date, end: date) -> pd.DataFrame:
    # yfinance end is exclusive; add one day to include end
    yf_end = end + timedelta(days=1)
    df = yf.download(
        symbol,
        start=start.isoformat(),
        end=yf_end.isoformat(),
        interval="1d",
        auto_adjust=False,
        progress=False,
        actions=False,
        threads=True,
    )

    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()
    if "Date" not in df.columns:
        raise RuntimeError("unexpected yfinance output: missing Date column")

    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )

    df["trade_date"] = pd.to_datetime(df["Date"]).dt.date
    keep = ["trade_date", "open", "high", "low", "close", "adj_close", "volume"]
    df = df[keep]

    # normalize types / missing values
    df = df.dropna(subset=["trade_date", "open", "high", "low", "close"])
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

    return df


def _chunked(rows: list[dict], size: int):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="AAPL", help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--years", type=int, default=10, help="How many years back from end date")
    parser.add_argument("--start", type=date.fromisoformat, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=date.fromisoformat, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--chunk", type=int, default=500, help="Upsert batch size")
    args = parser.parse_args()

    symbol = str(args.symbol).strip().upper()
    if not symbol:
        raise SystemExit("symbol is required")

    end = args.end or date.today()
    start = args.start or _years_ago(end, int(args.years))
    if start > end:
        raise SystemExit("start must be <= end")

    print(f"Downloading {symbol} daily data: {start} -> {end} ...")
    df = _download_daily(symbol, start, end)
    if df.empty:
        raise SystemExit("No data downloaded (empty)")

    # Ensure table exists
    Base.metadata.create_all(bind=engine)

    rows: list[dict] = []
    for r in df.itertuples(index=False):
        vol = None
        if getattr(r, "volume", None) is not None and pd.notna(r.volume):
            try:
                vol = int(r.volume)
            except Exception:
                vol = None

        adj_close = None
        if getattr(r, "adj_close", None) is not None and pd.notna(r.adj_close):
            adj_close = float(r.adj_close)

        rows.append(
            {
                "symbol": symbol,
                "trade_date": r.trade_date,
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": vol,
                "adj_close": adj_close,
            }
        )

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