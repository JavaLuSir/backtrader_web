import math

import backtrader as bt

STRATEGY_NAME = "Turtle Trading"
STRATEGY_DESCRIPTION = "海龟交易法则：唐奇安通道突破 + ATR 风险控制 + 加仓（可选做空）"


class TurtleTrading(bt.Strategy):
    """海龟交易法则（简化版，支持长线突破/风控/加仓）。

    规则（默认长多）：
    - 入场：收盘价突破过去 entry_period 天最高价（不含当天）
    - 出场：收盘价跌破过去 exit_period 天最低价（不含当天）
    - 波动率：ATR(atr_period)
    - 仓位：每个“单位”风险约为账户净值的 risk_pct（按 2*ATR 止损距离折算）
    - 止损：从最近一次加仓/开仓价回撤 stop_atr_mult * ATR 触发止损
    - 加仓：价格每上涨 add_atr_step * ATR 加 1 个单位，最多 max_units 个单位

    注：为了避免未来函数，唐奇安通道使用 [-1] 的昨日值比较。
    """

    params = (
        ("entry_period", 20),
        ("exit_period", 10),
        ("atr_period", 20),
        ("risk_pct", 0.01),
        ("stop_atr_mult", 2.0),
        ("add_atr_step", 0.5),
        ("max_units", 4),
        ("allow_short", False),
    )

    def __init__(self):
        self._order = None
        self._units = 0
        self._last_entry_price = None
        self._next_add_price = None
        self._stop_price = None

        self._donchian_high = bt.indicators.Highest(self.data.high, period=self.p.entry_period)
        self._donchian_low = bt.indicators.Lowest(self.data.low, period=self.p.entry_period)
        self._exit_low = bt.indicators.Lowest(self.data.low, period=self.p.exit_period)
        self._exit_high = bt.indicators.Highest(self.data.high, period=self.p.exit_period)

        self._atr = bt.indicators.ATR(self.data, period=self.p.atr_period)

    def _atr_value(self) -> float | None:
        v = float(self._atr[0])
        if not math.isfinite(v) or v <= 0:
            return None
        return v

    def _unit_size(self) -> int:
        atr_value = self._atr_value()
        if atr_value is None:
            return 0

        account_value = float(self.broker.getvalue())
        risk_cash = max(0.0, account_value * float(self.p.risk_pct))

        # 每个单位的止损距离按 stop_atr_mult * ATR 计算
        per_share_risk = atr_value * float(self.p.stop_atr_mult)
        if per_share_risk <= 0:
            return 0

        size = int(math.floor(risk_cash / per_share_risk))
        if size < 1:
            size = 1

        # 受现金约束（长仓）
        price = float(self.data.close[0])
        if math.isfinite(price) and price > 0 and not self.position:
            cash = float(self.broker.getcash())
            max_affordable = int(cash // price)
            if max_affordable > 0:
                size = min(size, max_affordable)

        return max(0, int(size))

    def _reset_state(self) -> None:
        self._units = 0
        self._last_entry_price = None
        self._next_add_price = None
        self._stop_price = None

    def _set_after_entry(self, entry_price: float, is_long: bool) -> None:
        atr_value = self._atr_value()
        if atr_value is None:
            return

        step = float(self.p.add_atr_step) * atr_value
        stop_dist = float(self.p.stop_atr_mult) * atr_value

        self._last_entry_price = float(entry_price)
        if is_long:
            self._next_add_price = self._last_entry_price + step
            self._stop_price = self._last_entry_price - stop_dist
        else:
            self._next_add_price = self._last_entry_price - step
            self._stop_price = self._last_entry_price + stop_dist

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            # 订单成交后更新加仓/止损参考价
            if self.position.size == 0:
                self._reset_state()
            else:
                # position.size > 0 -> long; < 0 -> short
                is_long = self.position.size > 0
                self._units = max(self._units, 1)
                self._set_after_entry(float(order.executed.price), is_long=is_long)

        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self._order = None

    def next(self):
        if self._order:
            return

        atr_value = self._atr_value()
        if atr_value is None:
            return

        close_price = float(self.data.close[0])

        # ===== 无持仓：寻找入场 =====
        if not self.position:
            self._reset_state()

            upper = float(self._donchian_high[-1])
            lower = float(self._donchian_low[-1])
            if math.isfinite(upper) and close_price > upper:
                size = self._unit_size()
                if size > 0:
                    self._order = self.buy(size=size)
                    self._units = 1
                    return

            if self.p.allow_short and math.isfinite(lower) and close_price < lower:
                size = self._unit_size()
                if size > 0:
                    self._order = self.sell(size=size)
                    self._units = 1
                    return

            return

        # ===== 有持仓：出场/止损/加仓 =====
        is_long = self.position.size > 0

        # 出场：唐奇安 exit 通道
        if is_long:
            exit_level = float(self._exit_low[-1])
            if math.isfinite(exit_level) and close_price < exit_level:
                self._order = self.close()
                return
        else:
            exit_level = float(self._exit_high[-1])
            if math.isfinite(exit_level) and close_price > exit_level:
                self._order = self.close()
                return

        # 止损：最近一次入场/加仓价的 2*ATR
        if self._stop_price is not None:
            if is_long and close_price < float(self._stop_price):
                self._order = self.close()
                return
            if (not is_long) and close_price > float(self._stop_price):
                self._order = self.close()
                return

        # 加仓：每上涨/下跌 add_atr_step * ATR
        if self._units >= int(self.p.max_units):
            return

        if self._next_add_price is None:
            # 避免状态丢失
            self._set_after_entry(close_price, is_long=is_long)

        if self._next_add_price is None:
            return

        should_add = close_price > float(self._next_add_price) if is_long else close_price < float(self._next_add_price)
        if not should_add:
            return

        size = self._unit_size()
        if size <= 0:
            return

        self._order = self.buy(size=size) if is_long else self.sell(size=size)
        self._units += 1


STRATEGY_CLASS = TurtleTrading