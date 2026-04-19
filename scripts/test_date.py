#!/usr/bin/env python3
"""测试前端发送的日期格式"""
import sys
sys.path.insert(0, '.')

from datetime import date
from btweb.db import SessionLocal
from btweb.data import load_ohlcv_dataframe
from btweb.schemas import BacktestRequest
from pathlib import Path
from btweb.strategy_loader import load_strategy_class
from btweb.backtest import run_backtest

# 模拟前端发送的日期字符串
start_date_str = "2024-01-01"  # 前端发送的是字符串
end_date_str = "2024-12-31"

# 解析日期
start_date = date.fromisoformat(start_date_str)
end_date = date.fromisoformat(end_date_str)

print(f"开始日期: {start_date}")
print(f"结束日期: {end_date}")

# 创建请求
request = BacktestRequest(
    strategy_id="sma_crossover.py",
    symbol="NVDA",
    cash=100000,
    start_date=start_date,
    end_date=end_date,
    commission=0.001
)

print(f"请求: {request}")

# 运行回测
session = SessionLocal()
df = load_ohlcv_dataframe(session, symbol="NVDA", start_date=request.start_date, end_date=request.end_date)

if df is not None:
    strategies_dir = Path("D:/backtrader_web/strategies")
    strategy_cls = load_strategy_class(strategies_dir, request.strategy_id)
    
    result = run_backtest(
        strategy_cls=strategy_cls,
        data=df,
        symbol=request.symbol,
        cash=request.cash,
        start_date=request.start_date,
        end_date=request.end_date,
        commission=request.commission
    )
    
    print(f"\n成功!")
    print(f"收益: {result.metrics.get('pnl')}")

session.close()