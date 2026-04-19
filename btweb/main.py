from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .backtest import run_backtest
from .config import load_settings
from .data import load_ohlcv_dataframe
from .db import engine, get_session
from .models import Base, StockInfo
from .schemas import BacktestRequest, BacktestResponse, StockInfoResponse
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
        # Keep web UI available even when DB is temporarily unavailable.
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


@app.get("/api/stocks")
def api_stocks(
    q: str = "", limit: int = 20, session: Session = Depends(get_session)
) -> list[StockInfoResponse]:
    """搜索股票列表，支持按代码或名称模糊匹配"""
    query = session.query(StockInfo)

    if q.strip():
        search_term = f"%{q.strip().upper()}%"
        query = query.filter(
            (StockInfo.symbol.like(search_term)) | (StockInfo.name.like(search_term))
        )

    results = query.order_by(StockInfo.symbol).limit(limit).all()

    stock_responses = [
        StockInfoResponse(
            symbol=stock.symbol,
            name=stock.name,
            exchange=stock.exchange,
            market=stock.market,
        )
        for stock in results
    ]
    return stock_responses


@app.get("/api/strategies")
def api_strategies() -> dict:
    return {"items": list_strategies(settings.strategies_dir)}


@app.post("/api/strategies/upload")
async def api_strategy_upload(
    file: UploadFile = File(...), session: Session = Depends(get_session)
) -> dict:
    """上传策略文件"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    filename = file.filename
    if not filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="只支持 .py 文件")
    
    # 安全检查：防止路径遍历
    safe_filename = Path(filename).name
    if ".." in safe_filename or "/" in safe_filename or "\\" in safe_filename:
        raise HTTPException(status_code=400, detail="无效的文件名")
    
    save_path = settings.strategies_dir / safe_filename
    
    content = await file.read()
    
    # 检查是否包含策略类
    if b"class " not in content and b"bt.Strategy" not in content:
        raise HTTPException(status_code=400, detail="文件不包含有效的策略类")
    
    # 写入文件
    save_path.write_bytes(content)
    
    return {"id": safe_filename, "name": safe_filename[:-3], "message": "上传成功"}


def _resolve_strategy_file(strategy_id: str) -> Path:
    base = settings.strategies_dir.resolve()
    path = (base / strategy_id).resolve()

    if path.suffix.lower() != ".py":
        raise HTTPException(status_code=400, detail="strategy_id must be a .py file")
    if base not in path.parents:
        raise HTTPException(status_code=400, detail="invalid strategy path")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="strategy not found")
    return path


@app.get("/api/strategies/source/{strategy_id}")
def api_strategy_source(strategy_id: str) -> dict:
    path = _resolve_strategy_file(strategy_id)
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        source = path.read_text(encoding="gbk", errors="replace")

    return {
        "id": strategy_id,
        "name": path.stem,
        "language": "python",
        "source": source,
    }


@app.delete("/api/strategies/{strategy_id}")
def api_strategy_delete(strategy_id: str) -> dict:
    """删除策略文件"""
    path = _resolve_strategy_file(strategy_id)
    path.unlink()
    return {"message": f"已删除 {strategy_id}"}


@app.put("/api/strategies/{strategy_id}")
async def api_strategy_update(strategy_id: str, request: Request) -> dict:
    """更新策略文件源码"""
    path = _resolve_strategy_file(strategy_id)
    body = await request.body()
    path.write_bytes(body)
    return {"message": "保存成功"}


@app.post("/api/backtest", response_model=BacktestResponse)
def api_backtest(
    payload: BacktestRequest, session: Session = Depends(get_session)
) -> BacktestResponse:
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
        session,
        symbol=symbol,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    if df is None or df.empty:
        raise HTTPException(
            status_code=400,
            detail=f"No OHLCV data found for {symbol} in the selected date range. Please ingest data first.",
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
        equity=result.equity,
        buys=result.buys,
        sells=result.sells,
        metrics=result.metrics,
        ohlcv=result.ohlcv,
    )
