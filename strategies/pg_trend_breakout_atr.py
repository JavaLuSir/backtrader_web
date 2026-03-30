"""
PG Trend Breakout ATR Strategy - 趋势突破ATR策略

【策略原理】
一种专注于大市值股票的趋势跟踪策略。
结合了价格突破、EMA趋势过滤和ATR移动止损。

【核心规则】
- 入场：价格突破55日高点 且 处于200日EMA上涨趋势中
- 出场：价格跌破20日低点 或 触发ATR移动止损
- 仓位管理：根据ATR止损距离计算仓位

【参数说明】
- entry_breakout: 入场突破周期（默认55日）
- exit_breakout: 出场通道周期（默认20日）
- trend_ema: 趋势过滤EMA周期（默认200日）
- atr_period: ATR计算周期（默认20日）
- atr_stop_mult: ATR止损倍数（默认3倍）
- risk_per_trade: 单笔风险比例（默认1%）
- max_alloc: 最大仓位比例（默认95%）

【仓位计算公式】
1. 按风险计算：账户风险金额 / (ATR × 止损倍数)
2. 按资金上限：账户净值 × 最大仓位比例 / 当前价格
3. 最终仓位 = min(按风险计算的仓位, 按资金上限的仓位)

【移动止损】
- 止损价 = 最高入场价 - (ATR × 倍数)
- 随着价格上涨，最高入场价不断更新

【适用场景】
- 大市值股票
- 日线级别交易
- 中长期趋势行情
"""

import math
import backtrader as bt

STRATEGY_NAME = "PG Trend Breakout ATR"
STRATEGY_DESCRIPTION = "55天突破入场 + 200EMA趋势过滤 + ATR移动止损"


class PGTrendBreakoutATR(bt.Strategy):
    """
    趋势突破ATR策略
    
    结合趋势过滤、突破入场和ATR移动止损的趋势跟踪策略。
    只做多，不做空。
    """
    
    # ===== 策略参数 =====
    params = (
        ("entry_breakout", 55),   # 入场突破周期（55日高点）
        ("exit_breakout", 20),    # 出场通道周期（20日低点）
        ("trend_ema", 200),       # 趋势过滤EMA周期
        ("atr_period", 20),       # ATR计算周期
        ("atr_stop_mult", 3.0),  # ATR止损倍数
        ("risk_per_trade", 0.01), # 单笔风险比例 1%
        ("max_alloc", 0.95),     # 最大仓位比例 95%
    )

    def __init__(self):
        """
        策略初始化
        
        创建所需的指标：
        - high_n: 55日最高价（入场参考）
        - low_n: 20日最低价（出场参考）
        - ema: 200日指数移动平均（趋势过滤）
        - atr: 平均真实波幅（仓位和止损计算）
        """
        # 订单状态跟踪
        self.order = None
        
        # 入场价格和持仓最高价
        self.entry_price = None              # 入场价格
        self.highest_since_entry = None       # 入场后的最高价（用于移动止损）
        
        # ===== 创建指标 =====
        # 入场参考：55日最高价
        self.high_n = bt.indicators.Highest(
            self.data.high, 
            period=self.p.entry_breakout
        )
        
        # 出场参考：20日最低价
        self.low_n = bt.indicators.Lowest(
            self.data.low, 
            period=self.p.exit_breakout
        )
        
        # 趋势过滤：200日EMA
        self.ema = bt.indicators.ExponentialMovingAverage(
            self.data.close, 
            period=self.p.trend_ema
        )
        
        # ATR指标：用于仓位计算和止损
        self.atr = bt.indicators.ATR(
            self.data, 
            period=self.p.atr_period
        )

    def notify_order(self, order):
        """
        订单状态通知
        
        处理订单完成后的状态更新
        """
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            if order.isbuy():
                # 买入成交，记录入场价
                self.entry_price = float(order.executed.price)
                self.highest_since_entry = self.entry_price
            elif order.issell() and self.position.size == 0:
                # 卖出平仓，重置状态
                self.entry_price = None
                self.highest_since_entry = None

        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def _calc_size(self):
        """
        计算开仓数量
        
        基于风险管理和资金限制的仓位计算：
        1. 按风险：账户可承受风险 / 止损距离
        2. 按资金上限：可用资金 / 当前价格
        3. 取两者较小值
        
        返回:
            合约数量
        """
        atr_value = float(self.atr[0])
        price = float(self.data.close[0])
        
        # 参数有效性检查
        if not math.isfinite(atr_value) or atr_value <= 0 or not math.isfinite(price) or price <= 0:
            return 0

        # 账户总资金
        equity = float(self.broker.getvalue())
        
        # 可承受风险金额
        risk_cash = equity * float(self.p.risk_per_trade)
        
        # 止损距离 = ATR × 倍数
        stop_distance = atr_value * float(self.p.atr_stop_mult)
        if stop_distance <= 0:
            return 0

        # 按风险计算的仓位
        by_risk = int(risk_cash / stop_distance)
        
        # 按资金上限计算的仓位
        by_alloc = int((equity * float(self.p.max_alloc)) / price)

        # 取两者较小值
        size = max(0, min(by_risk, by_alloc))
        
        # 确保至少买1手（如果有足够资金）
        if size < 1 and by_alloc >= 1:
            size = 1
        return size

    def next(self):
        """
        每个K线执行的策略逻辑
        
        【交易逻辑】
        1. 如果有待处理订单，跳过
        2. 有持仓时：
           - 更新入场后最高价
           - 检查出场信号（20日低点）
           - 检查ATR移动止损
        3. 无持仓时：
           - 检查趋势过滤（价格在200日EMA上方）
           - 检查突破信号（价格突破55日高点）
           - 计算仓位并买入
        """
        if self.order:
            return

        # 获取当前价格
        close = float(self.data.close[0])
        
        # 获取昨日通道价格
        prev_high = float(self.high_n[-1])  # 55日最高价
        prev_low = float(self.low_n[-1])   # 20日最低价

        # ===== 有持仓：检查出场 =====
        if self.position.size > 0:
            # 更新入场后的最高价
            if self.highest_since_entry is None:
                self.highest_since_entry = close
            else:
                self.highest_since_entry = max(float(self.highest_since_entry), close)
            
            # 计算ATR移动止损价位
            atr_value = float(self.atr[0])
            trailing_stop = (
                float(self.highest_since_entry) - float(self.p.atr_stop_mult) * atr_value
                if atr_value > 0
                else float("-inf")
            )
            
            # 出场条件1：价格跌破20日最低价
            exit_by_channel = close < prev_low if math.isfinite(prev_low) else False
            
            # 出场条件2：触发ATR移动止损
            exit_by_trailing = close < trailing_stop
            
            # 任一条件触发则平仓
            if exit_by_channel or exit_by_trailing:
                self.order = self.close()
                return

        # ===== 无持仓：检查入场 =====
        if self.position.size == 0:
            # 趋势过滤：价格在200日EMA上方（多头趋势）
            trend_ok = close > float(self.ema[0])
            
            # 突破信号：价格突破55日最高价
            breakout = close > prev_high if math.isfinite(prev_high) else False
            
            # 同时满足趋势过滤和突破则入场
            if trend_ok and breakout:
                size = self._calc_size()
                if size > 0:
                    self.order = self.buy(size=size)


# 导出策略类 - Web界面加载必需
STRATEGY_CLASS = PGTrendBreakoutATR