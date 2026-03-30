"""
MA Price Cross Strategy - 均线价格交叉策略

【策略原理】
基于价格与均线的交叉关系进行交易的简单趋势策略。
- 金叉买入：收盘价从下往上穿越均线
- 死叉卖出：收盘价从上往下穿越均线

【可选功能】
- 趋势过滤：使用更长周期的均线过滤，只在趋势同向时开仓
- 做空功能：支持做空交易（默认关闭）

【参数说明】
- ma_period: 交易均线周期（默认50日）
- trend_period: 趋势过滤均线周期（默认200日）
- use_trend_filter: 是否启用趋势过滤（默认开启）
- allow_short: 是否允许做空（默认关闭）

【适用场景】
- 趋势明显的市场
- 中长期交易
- 适合作为入门策略

【注意事项】
- 当前网站端还未实现参数动态配置，如需修改参数请直接修改代码默认值
"""

import backtrader as bt

STRATEGY_NAME = "MA Price Cross (50/200)"
STRATEGY_DESCRIPTION = "均线策略：价格上穿MA买入，下穿卖出（默认MA50；可用MA200做趋势过滤）"


class MAPriceCross(bt.Strategy):
    """
    均线价格交叉策略
    
    基于收盘价与均线的交叉关系进行交易。
    可选的趋势过滤功能可以避免逆势交易。
    """

    # ===== 策略参数 =====
    params = (
        ("ma_period", 50),       # 交易均线周期（短期）
        ("trend_period", 200),    # 趋势过滤均线周期（长期）
        ("use_trend_filter", True),  # 是否启用趋势过滤
        ("allow_short", False),   # 是否允许做空
    )

    def __init__(self):
        """
        策略初始化
        
        创建所需的指标：
        - ma: 交易用均线（默认50日）
        - trend_ma: 趋势过滤均线（默认200日）
        - cross: 价格与均线的交叉信号
        """
        # 订单状态跟踪，避免重复下单
        self.order = None
        
        # 创建交易均线（短期）
        self.ma = bt.indicators.SimpleMovingAverage(
            self.data.close, 
            period=self.p.ma_period
        )
        
        # 创建趋势过滤均线（长期）
        self.trend_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, 
            period=self.p.trend_period
        )
        
        # 创建交叉信号检测器
        # CrossOver(a, b): a上穿b返回>0，下穿b返回<0
        self.cross = bt.indicators.CrossOver(self.data.close, self.ma)

    def notify_order(self, order):
        """
        订单状态通知回调
        
        处理订单完成、取消、被拒等情况，重置订单状态。
        """
        # 等待提交的订单不处理
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        # 订单结束，重置订单状态
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        """
        每个K线执行的策略逻辑
        
        【交易逻辑】
        1. 如果有待处理订单，跳过
        2. 检查趋势过滤条件
        3. 无持仓时：检查开仓信号
        4. 有持仓时：检查平仓信号
        """
        # 如果有待处理订单，跳过本次检查
        if self.order:
            return
        
        # 获取当前收盘价
        close = self.data.close[0]
        
        # 趋势过滤条件
        # 多头趋势：收盘价在长期均线上方
        # 空头趋势：收盘价在长期均线下方
        trend_ok_long = True
        trend_ok_short = True
        if self.p.use_trend_filter:
            trend_ok_long = close > self.trend_ma[0]     # 多头：价格 > 200日均线
            trend_ok_short = close < self.trend_ma[0]    # 空头：价格 < 200日均线

        # ===== 无持仓：寻找开仓信号 =====
        if not self.position:
            # 买入信号：价格上穿均线 且 处于多头趋势
            if self.cross > 0 and trend_ok_long:
                self.order = self.buy()
                return
            
            # 卖出信号（做空）：价格下穿均线 且 处于空头趋势
            if self.p.allow_short and self.cross < 0 and trend_ok_short:
                self.order = self.sell()
                return
            
            return

        # ===== 有持仓：寻找平仓信号 =====
        if self.position.size > 0:
            # 多头持仓平仓条件：
            # 1. 价格下穿均线（金叉变死叉）
            # 2. 或趋势转空（趋势过滤启用时）
            if self.cross < 0 or (self.p.use_trend_filter and not trend_ok_long):
                self.order = self.close()
                return
        else:
            # 空头持仓平仓条件：
            # 1. 价格上穿均线（死叉变金叉）
            # 2. 或趋势转多（趋势过滤启用时）
            if self.cross > 0 or (self.p.use_trend_filter and not trend_ok_short):
                self.order = self.close()
                return


# 导出策略类 - Web界面加载必需
STRATEGY_CLASS = MAPriceCross