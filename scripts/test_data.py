#!/usr/bin/env python3
"""简单测试回测"""
import sys
sys.path.insert(0, '.')

from datetime import date
from btweb.db import SessionLocal
from btweb.data import load_ohlcv_dataframe

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
else:
    print(f"数据行数: {len(df)}")
    print(f"数据类型:\n{df.dtypes}")
    print(f"数据前3行:")
    print(df.head(3))
    
    # 检查是否有0值
    if (df['close'] == 0).any():
        print("警告：有收盘价为0的数据!")
    
    if df['close'].isna().any():
        print("警告：有NaN数据!")

session.close()