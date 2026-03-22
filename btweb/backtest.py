from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import backtrader as bt
import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    equity: list[dict]
    buys: list[dict]
    sells: list[dict]
    metrics: dict
    ohlcv: list[dict] = tuple()


def _wrap_strategy(strategy_cls: type[bt.Strategy]) -> type[bt.Strategy]:
    class Wrapped(strategy_cls):  # type: ignore[misc,valid-type]
        def __init__(self):
            super().__init__()
            self._web_equity: list[dict] = []
            self._web_markers: list[dict] = []
            self._web_ohlcv: list[dict] = []

        def next(self):
            super().next()
            dt = self.datas[0].datetime.date(0)
            self._web_equity.append(
                {"date": dt.isoformat(), "value": float(self.broker.getvalue())}
            )
            self._web_ohlcv.append({
                "time": dt.isoformat(),
                "open": float(self.data.open[0]),
                "high": float(self.data.high[0]),
                "low": float(self.data.low[0]),
                "close": float(self.data.close[0]),
                "volume": float(self.data.volume[0]),
            })

        def notify_order(self, order):
            super().notify_order(order)
            if order.status != order.Completed:
                return
            dt = self.datas[0].datetime.date(0)
            action = "buy" if order.isbuy() else "sell"
            self._web_markers.append(
                {
                    "date": dt.isoformat(),
                    "action": action,
                    "price": float(order.executed.price),
                    "size": float(order.executed.size),
                    "value": float(self.broker.getvalue()),
                }
            )

    Wrapped.__name__ = f"WebWrapped_{strategy_cls.__name__}"
    return Wrapped


def run_backtest(
    *,
    strategy_cls: type[bt.Strategy],
    data: pd.DataFrame,
    symbol: str,
    cash: float,
    start_date: date,
    end_date: date,
    commission: float = 0.001,
) -> BacktestResult:
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=commission)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)

    feed = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(feed, name=symbol)

    wrapped = _wrap_strategy(strategy_cls)
    cerebro.addstrategy(wrapped)

    results = cerebro.run()
    strat = results[0]

    equity: list[dict] = getattr(strat, "_web_equity", [])
    ohlcv: list[dict] = getattr(strat, "_web_ohlcv", [])
    markers: list[dict] = getattr(strat, "_web_markers", [])
    buys = [m for m in markers if m.get("action") == "buy"]
    sells = [m for m in markers if m.get("action") == "sell"]

    end_value = float(strat.broker.getvalue())
    pnl = end_value - cash
    metrics = {
        "symbol": symbol,
        "strategy": strategy_cls.__name__,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "start_cash": float(cash),
        "end_value": end_value,
        "pnl": float(pnl),
        "return_pct": float((pnl / cash) * 100.0) if cash else 0.0,
        "buy_count": len(buys),
        "sell_count": len(sells),
    }

    return BacktestResult(equity=equity, buys=buys, sells=sells, metrics=metrics, ohlcv=ohlcv)

