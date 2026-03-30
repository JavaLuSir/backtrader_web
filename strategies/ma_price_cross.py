import backtrader as bt

STRATEGY_NAME = "MA Price Cross (50/200)"
STRATEGY_DESCRIPTION = "均线策略：价格上穿MA买入，下穿卖出（默认MA50；可用MA200做趋势过滤）"


class MAPriceCross(bt.Strategy):
    """均线策略（价格与均线交叉）。

    - 入场：收盘价上穿 ma_period 的均线 -> 买入
    - 出场：收盘价下穿 ma_period 的均线 -> 卖出/平仓

    可选趋势过滤（默认开启）：
    - 仅在收盘价位于 trend_period 均线同方向时开仓（多头：close > trend_ma）

    注意：当前网站端还没有做“网页传参”，如需改周期直接改 params 默认值即可。
    """

    params = (
        ("ma_period", 50),
        ("trend_period", 200),
        ("use_trend_filter", True),
        ("allow_short", False),
    )

    def __init__(self):
        self.order = None
        self.ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.ma_period)
        self.trend_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.p.trend_period
        )

        # close 上穿/下穿 ma
        self.cross = bt.indicators.CrossOver(self.data.close, self.ma)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order:
            return

        close = self.data.close[0]
        trend_ok_long = True
        trend_ok_short = True
        if self.p.use_trend_filter:
            trend_ok_long = close > self.trend_ma[0]
            trend_ok_short = close < self.trend_ma[0]

        # ===== 无持仓：看开仓信号 =====
        if not self.position:
            if self.cross > 0 and trend_ok_long:
                self.order = self.buy()
                return

            if self.p.allow_short and self.cross < 0 and trend_ok_short:
                self.order = self.sell()
                return

            return

        # ===== 有持仓：看平仓信号 =====
        if self.position.size > 0:
            # 多头：下穿即平仓；趋势过滤也可作为兜底
            if self.cross < 0 or (self.p.use_trend_filter and not trend_ok_long):
                self.order = self.close()
                return
        else:
            # 空头：上穿即平仓；趋势过滤也可作为兜底
            if self.cross > 0 or (self.p.use_trend_filter and not trend_ok_short):
                self.order = self.close()
                return


STRATEGY_CLASS = MAPriceCross