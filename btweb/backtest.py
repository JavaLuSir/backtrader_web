from __future__ import annotations

import math
import statistics
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


def _max_drawdown(values: list[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    return float(max_dd)


def _compute_ratios(daily_returns: list[float]) -> tuple[float, float]:
    if len(daily_returns) < 2:
        return 0.0, 0.0

    mean_r = statistics.mean(daily_returns)
    try:
        vol = statistics.stdev(daily_returns)
    except statistics.StatisticsError:
        vol = 0.0

    sharpe = 0.0
    if vol and math.isfinite(vol) and vol > 0:
        sharpe = float((mean_r / vol) * math.sqrt(252.0))

    downside = [r for r in daily_returns if r < 0]
    sortino = 0.0
    if len(downside) >= 2:
        try:
            downside_dev = statistics.stdev(downside)
        except statistics.StatisticsError:
            downside_dev = 0.0
        if downside_dev and math.isfinite(downside_dev) and downside_dev > 0:
            sortino = float((mean_r / downside_dev) * math.sqrt(252.0))

    if not math.isfinite(sharpe):
        sharpe = 0.0
    if not math.isfinite(sortino):
        sortino = 0.0

    return sharpe, sortino


def _wrap_strategy(strategy_cls: type[bt.Strategy]) -> type[bt.Strategy]:
    class Wrapped(strategy_cls):  # type: ignore[misc,valid-type]
        def __init__(self):
            super().__init__()
            self._web_equity: list[dict] = []
            self._web_markers: list[dict] = []
            self._web_trades: list[dict] = []
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
            cash = float(self.broker.getcash())
            value = float(self.broker.getvalue())
            position_size = float(self.position.size)
            self._web_markers.append(
                {
                    "date": dt.isoformat(),
                    "action": action,
                    "price": float(order.executed.price),
                    "size": float(order.executed.size),
                    "cash": cash,
                    "value": value,
                    "position_size": position_size,
                }
            )

        def notify_trade(self, trade):
            super().notify_trade(trade)
            if not trade.isclosed:
                return
            dt = self.datas[0].datetime.date(0)
            self._web_trades.append(
                {
                    "date": dt.isoformat(),
                    "pnl": float(trade.pnl),
                    "pnlcomm": float(trade.pnlcomm),
                    "size": float(trade.size),
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
    trades: list[dict] = getattr(strat, "_web_trades", [])

    buys = [m for m in markers if m.get("action") == "buy"]
    sells = [m for m in markers if m.get("action") == "sell"]

    end_value = float(strat.broker.getvalue())
    pnl = end_value - cash

    values = [float(p.get("value")) for p in equity if p.get("value") is not None]
    daily_returns: list[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        cur = values[i]
        if prev and math.isfinite(prev) and prev != 0:
            daily_returns.append((cur / prev) - 1.0)

    max_dd = _max_drawdown(values)
    max_dd_pct = max_dd * 100.0

    years = (end_date - start_date).days / 365.25 if end_date >= start_date else 0.0
    annual_return = 0.0
    if years > 0 and cash > 0 and end_value > 0:
        annual_return = float((end_value / cash) ** (1.0 / years) - 1.0)

    sharpe, sortino = _compute_ratios(daily_returns)

    pnlcomms = [float(t.get("pnlcomm", 0.0)) for t in trades]
    wins = [x for x in pnlcomms if x > 0]
    losses = [x for x in pnlcomms if x < 0]

    win_rate_pct = 0.0
    if wins or losses:
        win_rate_pct = float((len(wins) / (len(wins) + len(losses))) * 100.0)

    avg_win = float(statistics.mean(wins)) if wins else 0.0
    avg_loss = float(abs(statistics.mean(losses))) if losses else 0.0
    avg_win_loss_ratio = float(avg_win / avg_loss) if avg_loss > 0 else 0.0

    calmar = 0.0
    if max_dd > 0:
        calmar = float(annual_return / max_dd)

    metrics = {
        "symbol": symbol,
        "strategy": strategy_cls.__name__,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "start_cash": float(cash),
        "end_value": end_value,
        "pnl": float(pnl),
        "return_pct": float((pnl / cash) * 100.0) if cash else 0.0,
        # 额外指标
        "annual_return_pct": float(annual_return * 100.0),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_drawdown_pct": float(max_dd_pct),
        "win_rate_pct": float(win_rate_pct),
        "avg_win_loss_ratio": float(avg_win_loss_ratio),
        "calmar": float(calmar),
        "trade_count": int(len(trades)),
        "buy_count": len(buys),
        "sell_count": len(sells),
    }

    return BacktestResult(equity=equity, buys=buys, sells=sells, metrics=metrics, ohlcv=ohlcv)