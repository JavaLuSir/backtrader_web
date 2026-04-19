from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    strategy_id: str = Field(
        ..., description="strategies/ 目录下的策略文件名，例如 sma_crossover.py"
    )
    symbol: str = Field(..., min_length=1, max_length=16)
    cash: float = Field(100000.0, gt=0)
    start_date: date
    end_date: date
    commission: float = Field(0.001, ge=0, le=0.1)


class BacktestResponse(BaseModel):
    equity: list[dict]
    buys: list[dict]
    sells: list[dict]
    metrics: dict
    ohlcv: list[dict] = []


class StockInfoResponse(BaseModel):
    symbol: str
    name: str
    exchange: str | None = None
    market: str | None = None
