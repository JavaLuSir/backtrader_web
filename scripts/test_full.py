#!/usr/bin/env python3
"""完整回测测试"""
import sys
sys.path.insert(0, '.')
from pathlib import Path

from datetime import date
from btweb.db import SessionLocal
from btweb.data import load_ohlcv_dataframe
from btweb.strategy_loader import load_strategy_class
from btweb.backtest import run_backtest

session = SessionLocal()

# 加载数据
df = load_ohlcv_dataframe(
    session,
    symbol="NVDA",
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31)
)

if df is None or df.empty:
    print("没有数据!")
    session.close()
    sys.exit(1)

print(f"数据行数: {len(df)}")

# 加载策略
strategies_dir = Path("D:/backtrader_web/strategies")
strategy_cls = load_strategy_class(strategies_dir, "sma_crossover.py")
print(f"策略类: {strategy_cls}")

# 运行回测
result = run_backtest(
    strategy_cls=strategy_cls,
    data=df,
    symbol="NVDA",
    cash=100000,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
    commission=0.001
)

print(f"回测完成!")
print(f"期末价值: {result.metrics.get('end_value')}")
print(f"收益: {result.metrics.get('pnl')}")
print(f"返回: {result.metrics.get('return_pct')}")
print(f"买: {result.metrics.get('buy_count')}, 卖: {result.metrics.get('sell_count')}")

session.close()