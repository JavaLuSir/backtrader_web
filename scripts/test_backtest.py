#!/usr/bin/env python3
"""简单测试回测"""
from datetime import date
from btweb.db import SessionLocal
from btweb.data import load_ohlcv_dataframe
from btweb.strategy_loader import load_strategy_class
from btweb.backtest import run_backtest

def main():
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
        return
    
    print(f"数据行数: {len(df)}")
    print(f"数据列: {list(df.columns)}")
    print(f"数据前3行:")
    print(df.head(3))
    
    # 加载策略
    from pathlib import Path
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
    
    session.close()

if __name__ == "__main__":
    main()