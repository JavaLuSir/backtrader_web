#!/usr/bin/env python3
"""导入股票信息到数据库

从 yfinance 获取股票信息，或者从 CSV 文件导入。

Example:
    # 从 yfinance 获取单个股票信息
    python scripts\import_stock_info.py --symbol AAPL

    # 批量导入股票代码列表
    python scripts\import_stock_info.py --symbols AAPL,GOOGL,MSFT

    # 从 CSV 文件导入 (A 股)
    python scripts\import_stock_info.py --csv stocks.csv
"""

from __future__ import annotations

import argparse
import csv
from typing import Any

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from btweb.db import SessionLocal, engine
from btweb.models import Base, StockInfo


def get_stock_info_from_yfinance(symbol: str) -> dict[str, Any] | None:
    """从 yfinance 获取股票信息"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        if not info:
            return None

        name = info.get("longName") or info.get("shortName") or symbol
        exchange = info.get("exchange")
        market = info.get("market")

        return {
            "symbol": symbol.upper(),
            "name": name,
            "exchange": exchange,
            "market": market,
        }
    except Exception as e:
        print(f"获取 {symbol} 信息失败：{e}")
        return None


def import_from_yfinance(symbols: list[str], session: Session) -> int:
    """从 yfinance 导入股票信息"""
    imported = 0

    for symbol in symbols:
        symbol = symbol.strip().upper()
        if not symbol:
            continue

        print(f"获取 {symbol} 信息...")
        info = get_stock_info_from_yfinance(symbol)

        if not info:
            print(f"  跳过：未获取到信息")
            continue

        stmt = mysql_insert(StockInfo).values(info)
        stmt = stmt.on_duplicate_key_update(
            name=stmt.inserted.name,
            exchange=stmt.inserted.exchange,
            market=stmt.inserted.market,
        )
        session.execute(stmt)
        imported += 1
        print(f"  导入成功：{info['name']}")

    session.commit()
    return imported


def import_from_csv(csv_path: str, session: Session) -> int:
    """从 CSV 文件导入股票信息

    CSV 格式:
    symbol,name,exchange,market
    600000.SS,浦发银行,SSE,
    000001.SZ,平安银行,SZSE,
    AAPL,Apple Inc,NASDAQ,
    """
    imported = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            symbol = row.get("symbol", "").strip().upper()
            name = row.get("name", "").strip()

            if not symbol or not name:
                continue

            info = {
                "symbol": symbol,
                "name": name,
                "exchange": row.get("exchange", "").strip() or None,
                "market": row.get("market", "").strip() or None,
            }

            stmt = mysql_insert(StockInfo).values(info)
            stmt = stmt.on_duplicate_key_update(
                name=stmt.inserted.name,
                exchange=stmt.inserted.exchange,
                market=stmt.inserted.market,
            )
            session.execute(stmt)
            imported += 1

    session.commit()
    return imported


def list_all_stocks(session: Session) -> int:
    """列出数据库中所有股票"""
    stmt = select(StockInfo).order_by(StockInfo.symbol)
    stocks = session.execute(stmt).scalars().all()

    if not stocks:
        print("数据库中没有股票信息")
        return 0

    print(f"共 {len(stocks)} 只股票:")
    for stock in stocks:
        exchange_str = f"({stock.exchange})" if stock.exchange else ""
        print(f"  {stock.symbol:10} {stock.name:20} {exchange_str}")

    return len(stocks)


def main() -> None:
    parser = argparse.ArgumentParser(description="导入股票信息到数据库")
    parser.add_argument("--symbol", help="单个股票代码")
    parser.add_argument("--symbols", help="多个股票代码，用逗号分隔")
    parser.add_argument("--csv", help="CSV 文件路径")
    parser.add_argument("--list", action="store_true", help="列出所有股票")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        if args.list:
            list_all_stocks(session)
            return

        imported = 0

        if args.symbol:
            imported = import_from_yfinance([args.symbol], session)

        if args.symbols:
            symbols = [s.strip() for s in args.symbols.split(",")]
            imported = import_from_yfinance(symbols, session)

        if args.csv:
            imported = import_from_csv(args.csv, session)

        if imported > 0:
            print(f"\n成功导入 {imported} 只股票")
        elif not args.list:
            print("未导入任何股票，使用 --help 查看用法")


if __name__ == "__main__":
    main()
