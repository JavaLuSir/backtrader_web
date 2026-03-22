"""
SMA Crossover Strategy - 简单移动平均线交叉策略

【策略原理】
- 金叉买入：短期均线（如20日）从下往上穿越长期均线（如50日）
- 死叉卖出：短期均线从上往下穿越长期均线

【参数说明】
- sma_fast: 快速均线周期（默认20）
- sma_slow: 慢速均线周期（默认50）

【适用场景】
- 趋势明显的市场
- 中长期交易
- 作为入门级策略，适合学习量化交易基础
"""

import backtrader as bt

STRATEGY_NAME = "SMA Crossover"
STRATEGY_DESCRIPTION = "20/50 均线交叉：金叉买入，死叉卖出"


class SMACrossover(bt.Strategy):
    """
    简单移动平均线交叉策略
    
    继承自 bt.Strategy，是 Backtrader 框架的标准策略格式。
    所有策略逻辑都在此类中实现。
    """
    
    params = (
        ("sma_fast", 20),   # 快速均线周期（短期）
        ("sma_slow", 50),   # 慢速均线周期（长期）
    )

    def __init__(self):
        """
        策略初始化
        
        在策略开始前调用，用于初始化指标和数据。
        此方法在回测开始时只执行一次。
        """
        # 创建快速移动平均线指标
        # self.data.close 表示使用收盘价
        # period 参数指定计算周期
        sma_fast = bt.indicators.SimpleMovingAverage(
            self.data.close, 
            period=self.p.sma_fast  # 使用参数中的快速均线周期
        )
        
        # 创建慢速移动平均线指标
        sma_slow = bt.indicators.SimpleMovingAverage(
            self.data.close, 
            period=self.p.sma_slow  # 使用参数中的慢速均线周期
        )
        
        # 创建交叉信号指标
        # CrossOver(a, b) 检测 a 上穿 b（返回>0）或下穿 b（返回<0）
        # > 0 表示金叉（a 从下往上穿越 b）
        # < 0 表示死叉（a 从上往下穿越 b）
        self.crossover = bt.indicators.CrossOver(sma_fast, sma_slow)
        
        # 订单状态跟踪变量
        # 用于避免在有未完成订单时重复下单
        self.order = None

    def next(self):
        """
        每个K线执行的策略逻辑
        
        回测过程中，每个新的K线（即每个交易日）都会调用此方法。
        在此方法中实现买卖逻辑。
        """
        # 如果有待处理的订单，跳过本次检查
        # 这是为了避免在订单执行期间重复下单
        if self.order:
            return
        
        # ===== 买入条件：金光叉 =====
        # self.crossover > 0 表示快速均线上穿慢速均线（金叉）
        # not self.position 表示当前没有持仓
        if self.crossover > 0 and not self.position:
            # 下买入单
            # self.buy() 返回订单对象，用于后续跟踪
            self.order = self.buy()
        
        # ===== 卖出条件：死叉 =====
        # self.crossover < 0 表示快速均线下穿慢速均线（死叉）
        # self.position 表示当前有持仓
        elif self.crossover < 0 and self.position:
            # 下卖出单
            self.order = self.sell()

    def notify_order(self, order):
        """
        订单状态通知回调
        
        当订单状态发生变化时（如提交、成交、取消等）会自动调用此方法。
        用于跟踪订单执行状态。
        
        参数:
            order: 订单对象，包含订单状态和详情
        """
        # 检查订单是否已完成、取消、保证金不足或被拒绝
        # 如果是其中任何一种状态，说明订单已结束，重置订单状态
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.order = None  # 重置订单状态，允许新订单


# 导出策略类
# 这是必须的！Web界面会根据这个变量加载策略
STRATEGY_CLASS = SMACrossover

