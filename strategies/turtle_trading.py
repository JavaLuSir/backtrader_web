"""
Turtle Trading Strategy - 海龟交易法则

【策略原理】
经典的海龟交易法则，一种基于价格通道突破的趋势跟踪策略。
由理查德·丹尼斯在1980年代创立。

【核心规则】
- 入场：价格突破过去N日最高价（做多）或跌破最低价（做空）
- 出场：价格跌破过去M日最低价（多头）或突破最高价（空头）
- 仓位管理：根据ATR计算风险，每次交易风险控制在账户净值的固定比例
- 止损：入场价回撤2倍ATR
- 加仓：价格每朝有利方向移动0.5倍ATR时加仓

【参数说明】
- entry_period: 入场通道周期（默认20日）
- exit_period: 出场通道周期（默认10日）
- atr_period: ATR计算周期（默认20日）
- risk_pct: 单笔风险比例（默认1%）
- stop_atr_mult: 止损ATR倍数（默认2倍）
- add_atr_step: 加仓ATR步长（默认0.5倍）
- max_units: 最大持仓单位数（默认4个）
- allow_short: 是否允许做空（默认关闭）

【仓位计算公式】
单位数量 = 账户风险金额 / (ATR × 止损倍数)
其中：账户风险金额 = 账户净值 × risk_pct

【适用场景】
- 趋势明显的市场
- 高波动期
- 中长期交易

【注意事项】
- 为避免未来函数，使用昨日的通道数据进行比较
- ATR用于衡量市场波动性，帮助动态调整仓位
"""

import math
import backtrader as bt

STRATEGY_NAME = "Turtle Trading"
STRATEGY_DESCRIPTION = "海龟交易法则：唐奇安通道突破 + ATR 风险控制 + 加仓（可选做空）"


class TurtleTrading(bt.Strategy):
    """
    海龟交易法则策略
    
    基于唐奇安通道突破和ATR风险控制的趋势跟踪策略。
    支持分批加仓和动态止损。
    """
    
    # ===== 策略参数 =====
    params = (
        ("entry_period", 20),    # 入场通道周期（20日高点/低点）
        ("exit_period", 10),      # 出场通道周期（10日低点/高点）
        ("atr_period", 20),       # ATR计算周期
        ("risk_pct", 0.01),      # 单笔风险比例 1%
        ("stop_atr_mult", 2.0),  # 止损ATR倍数
        ("add_atr_step", 0.5),   # 加仓ATR步长
        ("max_units", 4),        # 最大持仓单位数
        ("allow_short", False),  # 是否允许做空
    )

    def __init__(self):
        """
        策略初始化
        
        创建所需的指标：
        - 唐奇安通道（入场）：20日最高/最低价
        - 唐奇安通道（出场）：10日最低/最高价
        - ATR：平均真实波幅
        """
        # 订单状态跟踪
        self._order = None
        
        # 持仓状态
        self._units = 0              # 当前持仓单位数
        self._last_entry_price = None  # 最后一次入场价格
        self._next_add_price = None    # 下一次加仓价格
        self._stop_price = None         # 止损价格
        
        # ===== 创建唐奇安通道指标 =====
        # 入场通道：20日最高价/最低价
        self._donchian_high = bt.indicators.Highest(
            self.data.high, 
            period=self.p.entry_period
        )
        self._donchian_low = bt.indicators.Lowest(
            self.data.low, 
            period=self.p.entry_period
        )
        
        # 出场通道：10日最低价/最高价
        self._exit_low = bt.indicators.Lowest(
            self.data.low, 
            period=self.p.exit_period
        )
        self._exit_high = bt.indicators.Highest(
            self.data.high, 
            period=self.p.exit_period
        )
        
        # ATR指标：衡量市场波动性
        self._atr = bt.indicators.ATR(
            self.data, 
            period=self.p.atr_period
        )

    def _atr_value(self) -> float | None:
        """
        获取当前ATR值
        
        返回:
            ATR值，如果无效返回None
        """
        v = float(self._atr[0])
        if not math.isfinite(v) or v <= 0:
            return None
        return v

    def _unit_size(self) -> int:
        """
        计算每次开仓/加仓的合约数量
        
        基于风险管理的仓位计算：
        1. 计算账户可承受的风险金额
        2. 根据ATR和止损倍数计算每股风险
        3. 得到合约数量
        4. 受现金约束限制
        
        返回:
            合约数量
        """
        atr_value = self._atr_value()
        if atr_value is None:
            return 0

        # 账户总资金
        account_value = float(self.broker.getvalue())
        # 可承受风险金额 = 账户净值 × 风险比例
        risk_cash = max(0.0, account_value * float(self.p.risk_pct))

        # 每股风险 = ATR × 止损倍数
        per_share_risk = atr_value * float(self.p.stop_atr_mult)
        if per_share_risk <= 0:
            return 0

        # 计算合约数量（向下取整）
        size = int(math.floor(risk_cash / per_share_risk))
        if size < 1:
            size = 1

        # 受现金约束限制（首次开仓时）
        price = float(self.data.close[0])
        if math.isfinite(price) and price > 0 and not self.position:
            cash = float(self.broker.getcash())
            max_affordable = int(cash // price)
            if max_affordable > 0:
                size = min(size, max_affordable)

        return max(0, int(size))

    def _reset_state(self) -> None:
        """
        重置持仓状态
        
        平仓后调用，清空所有持仓相关状态
        """
        self._units = 0
        self._last_entry_price = None
        self._next_add_price = None
        self._stop_price = None

    def _set_after_entry(self, entry_price: float, is_long: bool) -> None:
        """
        入场/加仓后更新状态
        
        设置下一次加仓价格和止损价格
        
        参数:
            entry_price: 入场价格
            is_long: 是否做多
        """
        atr_value = self._atr_value()
        if atr_value is None:
            return

        # 加仓步长 = 0.5 × ATR
        step = float(self.p.add_atr_step) * atr_value
        # 止损距离 = 2 × ATR
        stop_dist = float(self.p.stop_atr_mult) * atr_value

        self._last_entry_price = float(entry_price)
        if is_long:
            # 多头：加仓价位 = 入场价 + 步长
            # 止损价位 = 入场价 - 止损距离
            self._next_add_price = self._last_entry_price + step
            self._stop_price = self._last_entry_price - stop_dist
        else:
            # 空头：加仓价位 = 入场价 - 步长
            # 止损价位 = 入场价 + 止损距离
            self._next_add_price = self._last_entry_price - step
            self._stop_price = self._last_entry_price + stop_dist

    def notify_order(self, order):
        """
        订单状态通知
        
        处理订单完成后的状态更新
        """
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            # 订单成交后更新状态
            if self.position.size == 0:
                # 平仓完成，重置状态
                self._reset_state()
            else:
                # 开仓/加仓完成，更新持仓信息
                is_long = self.position.size > 0
                self._units = max(self._units, 1)
                self._set_after_entry(float(order.executed.price), is_long=is_long)

        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self._order = None

    def next(self):
        """
        每个K线执行的策略逻辑
        
        【交易逻辑】
        1. 如果有待处理订单，跳过
        2. 获取ATR值
        3. 无持仓时：寻找入场信号（突破20日高点）
        4. 有持仓时：
           - 检查出场信号（跌破10日低点）
           - 检查止损信号
           - 检查加仓信号
        """
        if self._order:
            return

        atr_value = self._atr_value()
        if atr_value is None:
            return

        close_price = float(self.data.close[0])

        # ===== 无持仓：寻找入场信号 =====
        if not self.position:
            # 重置状态
            self._reset_state()
            
            # 获取昨日唐奇安通道上轨
            upper = float(self._donchian_high[-1])
            lower = float(self._donchian_low[-1])
            
            # 多头入场：价格突破20日最高价
            if math.isfinite(upper) and close_price > upper:
                size = self._unit_size()
                if size > 0:
                    self._order = self.buy(size=size)
                    self._units = 1
                    return
            
            # 空头入场：价格跌破20日最低价
            if self.p.allow_short and math.isfinite(lower) and close_price < lower:
                size = self._unit_size()
                if size > 0:
                    self._order = self.sell(size=size)
                    self._units = 1
                    return
            
            return

        # ===== 有持仓：出场/止损/加仓 =====
        is_long = self.position.size > 0

        # ===== 出场信号：唐奇安出场通道 =====
        if is_long:
            # 多头出场：价格跌破10日最低价
            exit_level = float(self._exit_low[-1])
            if math.isfinite(exit_level) and close_price < exit_level:
                self._order = self.close()
                return
        else:
            # 空头出场：价格突破10日最高价
            exit_level = float(self._exit_high[-1])
            if math.isfinite(exit_level) and close_price > exit_level:
                self._order = self.close()
                return

        # ===== 止损检查 =====
        if self._stop_price is not None:
            if is_long and close_price < float(self._stop_price):
                # 多头止损
                self._order = self.close()
                return
            if (not is_long) and close_price > float(self._stop_price):
                # 空头止损
                self._order = self.close()
                return

        # ===== 加仓检查 =====
        # 已达最大单位数，不再加仓
        if self._units >= int(self.p.max_units):
            return

        # 避免状态丢失
        if self._next_add_price is None:
            self._set_after_entry(close_price, is_long=is_long)

        if self._next_add_price is None:
            return

        # 检查是否达到加仓条件
        should_add = (close_price > float(self._next_add_price) if is_long 
                     else close_price < float(self._next_add_price))
        if not should_add:
            return

        size = self._unit_size()
        if size <= 0:
            return

        # 执行加仓
        self._order = self.buy(size=size) if is_long else self.sell(size=size)
        self._units += 1


# 导出策略类 - Web界面加载必需
STRATEGY_CLASS = TurtleTrading