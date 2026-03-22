from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .backtest import run_backtest
from .config import load_settings
from .data import load_ohlcv_dataframe
from .db import engine, get_session
from .models import Base
from .schemas import BacktestRequest, BacktestResponse
from .strategy_loader import list_strategies, load_strategy_class

logger = logging.getLogger("btweb")
settings = load_settings()

app = FastAPI(title="Backtrader Web")


@app.on_event("startup")
def _startup_init() -> None:
    if not settings.auto_init_db:
        return
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("db tables ensured")
    except Exception as exc:  # noqa: BLE001
        # DB 不通时不要阻塞网页启动（用户可能只是想先看页面）
        logger.warning("db init skipped: %s", exc)


static_dir = settings.static_dir
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    index_file = (static_dir / "index.html").resolve()
    if not index_file.exists():
        raise HTTPException(status_code=500, detail="static/index.html not found")
    return FileResponse(index_file)


@app.get("/api/health")
def health(session: Session = Depends(get_session)) -> dict:
    session.execute(text("SELECT 1"))
    return {"ok": True}


@app.get("/api/strategies")
def api_strategies() -> dict:
    return {"items": list_strategies(settings.strategies_dir)}


@app.post("/api/backtest", response_model=BacktestResponse)
def api_backtest(payload: BacktestRequest, session: Session = Depends(get_session)) -> BacktestResponse:
    symbol = payload.symbol.strip().upper()
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")

    try:
        strategy_cls = load_strategy_class(settings.strategies_dir, payload.strategy_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="strategy not found")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))

    df = load_ohlcv_dataframe(
        session, symbol=symbol, start_date=payload.start_date, end_date=payload.end_date
    )
    if df is None or df.empty:
        raise HTTPException(
            status_code=400,
            detail=f"数据库中没有 {symbol} 在该日期范围内的数据，请先采集入库",
        )

    result = run_backtest(
        strategy_cls=strategy_cls,
        data=df,
        symbol=symbol,
        cash=payload.cash,
        start_date=payload.start_date,
        end_date=payload.end_date,
        commission=payload.commission,
    )
    return BacktestResponse(
        equity=result.equity, buys=result.buys, sells=result.sells, metrics=result.metrics
    )

