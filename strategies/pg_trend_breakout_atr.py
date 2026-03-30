import math

import backtrader as bt

STRATEGY_NAME = "PG Trend Breakout ATR"
STRATEGY_DESCRIPTION = "55-day breakout entry + 200EMA trend filter + ATR trailing risk control"


class PGTrendBreakoutATR(bt.Strategy):
    """Trend-following long-only strategy for large-cap daily bars.

    Entry:
    - Close breaks above previous N-day high
    - Close is above long-term EMA trend filter

    Exit:
    - Close breaks below previous M-day low
    - Or ATR trailing stop is hit

    Position sizing:
    - Risk-based sizing from ATR stop distance
    - Capped by max account allocation
    """

    params = (
        ("entry_breakout", 55),
        ("exit_breakout", 20),
        ("trend_ema", 200),
        ("atr_period", 20),
        ("atr_stop_mult", 3.0),
        ("risk_per_trade", 0.01),
        ("max_alloc", 0.95),
    )

    def __init__(self):
        self.order = None
        self.entry_price = None
        self.highest_since_entry = None

        self.high_n = bt.indicators.Highest(self.data.high, period=self.p.entry_breakout)
        self.low_n = bt.indicators.Lowest(self.data.low, period=self.p.exit_breakout)
        self.ema = bt.indicators.ExponentialMovingAverage(self.data.close, period=self.p.trend_ema)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            if order.isbuy():
                self.entry_price = float(order.executed.price)
                self.highest_since_entry = self.entry_price
            elif order.issell() and self.position.size == 0:
                self.entry_price = None
                self.highest_since_entry = None

        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def _calc_size(self):
        atr_value = float(self.atr[0])
        price = float(self.data.close[0])
        if not math.isfinite(atr_value) or atr_value <= 0 or not math.isfinite(price) or price <= 0:
            return 0

        equity = float(self.broker.getvalue())
        risk_cash = equity * float(self.p.risk_per_trade)
        stop_distance = atr_value * float(self.p.atr_stop_mult)
        if stop_distance <= 0:
            return 0

        by_risk = int(risk_cash / stop_distance)
        by_alloc = int((equity * float(self.p.max_alloc)) / price)

        size = max(0, min(by_risk, by_alloc))
        if size < 1 and by_alloc >= 1:
            size = 1
        return size

    def next(self):
        if self.order:
            return

        close = float(self.data.close[0])
        prev_high = float(self.high_n[-1])
        prev_low = float(self.low_n[-1])

        if self.position.size > 0:
            self.highest_since_entry = (
                close
                if self.highest_since_entry is None
                else max(float(self.highest_since_entry), close)
            )

            atr_value = float(self.atr[0])
            trailing_stop = (
                float(self.highest_since_entry) - float(self.p.atr_stop_mult) * atr_value
                if atr_value > 0
                else float("-inf")
            )

            exit_by_channel = close < prev_low if math.isfinite(prev_low) else False
            exit_by_trailing = close < trailing_stop

            if exit_by_channel or exit_by_trailing:
                self.order = self.close()
                return

        if self.position.size == 0:
            trend_ok = close > float(self.ema[0])
            breakout = close > prev_high if math.isfinite(prev_high) else False
            if trend_ok and breakout:
                size = self._calc_size()
                if size > 0:
                    self.order = self.buy(size=size)


STRATEGY_CLASS = PGTrendBreakoutATR