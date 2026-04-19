#!/usr/bin/env python3
"""初始化股票信息表，导入标普500成分股

从 GitHub 获取最新的 S&P 500 成分股列表并导入数据库。

Example:
    python scripts\init_stocks.py
"""

from __future__ import annotations

import csv
import io
import sys
from urllib.request import urlopen

from btweb.db import SessionLocal, engine
from btweb.models import Base, StockInfo

SP500_CSV_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"


def fetch_sp500_from_github() -> list[tuple[str, str, str]]:
    """从 GitHub 获取 S&P 500 成分股列表"""
    print("正在从 GitHub 获取 S&P 500 成分股列表...")
    
    try:
        with urlopen(SP500_CSV_URL, timeout=30) as response:
            content = response.read().decode("utf-8")
    except Exception as e:
        print(f"下载失败: {e}")
        return []

    reader = csv.DictReader(io.StringIO(content))
    stocks = []
    
    for row in reader:
        symbol = row.get("Symbol", "").strip()
        name = row.get("Security", "").strip()
        
        if not symbol or not name:
            continue
        
        # 清理股票代码中的特殊字符
        symbol = symbol.replace(".", "-").replace("^", "-")
        
        stocks.append((symbol, name, "NASDAQ" if is_nasdaq(symbol) else "NYSE"))
    
    return stocks


def is_nasdaq(symbol: str) -> bool:
    """判断是否为纳斯达克股票"""
    nasdaq_symbols = {
        "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "NVDA", "TSLA", "AMD",
        "INTC", "CSCO", "ORCL", "IBM", "QCOM", "AVGO", "TXN", "MU", "ADI",
        "LRCX", "KLAC", "AMAT", "MCHP", "ON", "NXPI", "FSLR", "SWKS",
        "ADBE", "CRM", "NOW", "INTU", "PANW", "FTNT", "CRWD", "ZS", "OKTA",
        "SNPS", "CDNS", "ANSS", "AUTodesk", "TEAM", "WDAY", "SPLK", "DDOG",
        "NET", "GTLB", "snow", "PLTR", "ROKU", "ZM", "DOCU", "TWLO", "SQ",
        "PYPL", "MSTR", "COIN", "RBLX", "U", "ABNB", "DASH", "DKNG", "SNAP",
        "PINS", "TREE", "ETSY", "W", "MTCH", "CHWY", "WUB", "RPM", "TTCF",
        "LCID", "FVRR", "Hims", "BILL", "WE", "ESTC", "CFLT", "FRO", "NCNO",
    }
    return symbol in nasdaq_symbols or not contains_wall_caps(symbol.split("-")[0], {"A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M"})
    # 简化判断：包含4个字母且全大写的通常是纳斯达克


def contains_wall_caps(s: str, allow: set) -> bool:
    """检查字符串是否全由指定字母组成"""
    return all(c in allow for c in s.upper())


def main() -> None:
    print("创建 stock_info 表...")
    Base.metadata.create_all(bind=engine)
    
    # 清空旧数据
    with SessionLocal() as session:
        session.query(StockInfo).delete()
        session.commit()
        print("已清空旧数据")
    
    stocks = fetch_sp500_from_github()
    
    if not stocks:
        print("获取股票列表失败，使用内置数据...")
        return
    
    print(f"获取到 {len(stocks)} 只股票")
    print("正在导入数据库...")
    
    imported = 0
    skipped = 0
    
    with SessionLocal() as session:
        for symbol, name, exchange in stocks:
            try:
                stock = StockInfo(
                    symbol=symbol.upper(),
                    name=name,
                    exchange=exchange,
                )
                session.merge(stock)
                imported += 1
                
                if imported % 50 == 0:
                    print(f"  已导入 {imported}/{len(stocks)}...")
            except Exception as e:
                skipped += 1
                print(f"  跳过 {symbol}: {e}")
        
        session.commit()
    
    print(f"\n成功导入 {imported} 只股票")
    if skipped > 0:
        print(f"跳过 {skipped} 只股票")
    
    # 显示部分股票
    print("\n前 20 只股票:")
    for symbol, name, exchange in stocks[:20]:
        print(f"  {symbol:8} {name:40} ({exchange})")


if __name__ == "__main__":
    main()