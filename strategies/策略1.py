#!/usr/bin/env python3
"""
Backtrader AAPL 10年回测示例 (2016-2026)

策略：简单移动平均线交叉策略 (SMA Crossover)
- 买入信号：短期均线(如20日)上穿长期均线(如50日) -> 金叉
- 卖出信号：短期均线下穿长期均线 -> 死叉

运行方式：
    python3 backtrader_aapl_backtest.py
"""

import backtrader as bt          # 回测框架
import datetime                 # 日期处理
import yfinance as yf            # Yahoo Finance 获取股票数据
import pandas as pd              # 数据处理
import matplotlib.pyplot as plt  # 绘图
import matplotlib.dates as mdates  # 日期格式化


# ==================== 策略定义 ====================
class SimpleStrategy(bt.Strategy):
    """
    简单移动平均线交叉策略
    
    原理：
    - 当短期均线从下往上穿越长期均线时买入（金叉）
    - 当短期均线从上往下穿越长期均线时卖出（死叉）
    """
    
    # 策略参数
    params = (
        ('sma_fast', 20),   # 快速均线周期 (短期)
        ('sma_slow', 50),   # 慢速均线周期 (长期)
    )
    
    def __init__(self):
        """策略初始化"""
        # 获取收盘价数据
        self.dataclose = self.datas[0].close
        
        # 订单状态跟踪（避免重复下单）
        self.order = None
        
        # 计算移动平均线指标
        # SimpleMovingAverage 是 backtrader 内置指标
        self.sma_fast = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.sma_fast)  # 20日均线
        self.sma_slow = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.sma_slow)  # 50日均线
        
        # 交叉信号指标：检测两根均线是否交叉
        # > 0 表示金叉（买入），< 0 表示死叉（卖出）
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)
    
    def log(self, txt, dt=None):
        """日志输出"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} - {txt}')
    
    def notify_order(self, order):
        """订单状态通知"""
        # 订单提交或接受中，等待执行
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        # 订单已完成
        if order.status in [order.Completed]:
            if order.isbuy():
                # 买入订单完成
                self.log(f'买入执行: 价格 {order.executed.price:.2f}')
            elif order.issell():
                # 卖出订单完成
                self.log(f'卖出执行: 价格 {order.executed.price:.2f}')
        
        # 重置订单状态
        self.order = None
    
    def next(self):
        """每个交易日执行的策略逻辑"""
        # 如果有待处理订单，跳过
        if self.order:
            return
        
        # ===== 交易逻辑 =====
        
        # 买入条件：金叉 且 当前无持仓
        # self.crossover > 0 表示快速均线刚刚上穿慢速均线
        # not self.position 表示没有持仓
        if self.crossover > 0 and not self.position:
            self.log(f'买入信号! 价格: {self.dataclose[0]:.2f}')
            self.order = self.buy()  # 下买入单
        
        # 卖出条件：死叉 且 当前有持仓
        # self.crossover < 0 表示快速均线刚刚下穿慢速均线
        # self.position.size > 0 表示有持仓
        elif self.crossover < 0 and self.position.size > 0:
            self.log(f'卖出信号! 价格: {self.dataclose[0]:.2f}')
            self.order = self.sell()  # 下卖出单


# ==================== 回测主函数 ====================
def run_backtest():
    """
    运行回测的主函数
    
    步骤：
    1. 创建 Cerebro 引擎
    2. 设置初始资金和佣金
    3. 加载股票数据
    4. 添加策略
    5. 添加分析器（计算绩效指标）
    6. 运行回测
    7. 输出结果和绘图
    """
    
    # ----- 1. 创建 Cerebro 引擎 -----
    # Cerebro 是 backtrader 的核心，相当于大脑
    cerebro = bt.Cerebro()
    
    # ----- 2. 设置初始资金和佣金 -----
    # 初始资金 10 万美元
    cerebro.broker.setcash(100000.0)
    
    # 设置佣金为 0.1%（千分之一）
    # 每次买入/卖出都会扣除佣金
    cerebro.broker.setcommission(commission=0.001)
    
    # ----- 3. 获取 AAPL 数据 (10年) -----
    start_date = datetime.datetime(2016, 3, 1)  # 开始日期
    end_date = datetime.datetime(2026, 3, 1)    # 结束日期
    
    # 使用 yfinance 下载 AAPL 历史数据
    ticker = yf.Ticker('AAPL')
    data = ticker.history(start=start_date, end=end_date)
    
    if data.empty:
        print("错误: 无法获取数据")
        return
    
    # ----- 数据预处理 -----
    # 重置索引，把 Date 从索引变为列
    data = data.reset_index()
    
    # 保存绘图数据（转换日期时区）
    plot_data = data.copy()
    plot_data['Date'] = pd.to_datetime(plot_data['Date']).dt.tz_localize(None)
    plot_data = plot_data.set_index('Date')
    
    # backtrader 用的数据副本
    bt_data = data.copy()
    
    # ----- 4. 转换为 Backtrader 数据格式 -----
    # PandasData 是 backtrader 提供的 pandas 数据接口
    bt_feed = bt.feeds.PandasData(
        dataname=bt_data,
        datetime=0,        # 日期列索引（第0列）
        open='Open',       # 开盘价列名
        high='High',       # 最高价列名
        low='Low',         # 最低价列名
        close='Close',     # 收盘价列名
        volume='Volume',   # 成交量列名
        openinterest=-1   # 持仓量（-1表示没有这列）
    )
    
    # 将数据添加到 Cerebro
    cerebro.adddata(bt_feed)
    
    # 添加策略到 Cerebro
    cerebro.addstrategy(SimpleStrategy)
    
    # ----- 5. 添加分析器 -----
    # 这些分析器会在回测结束后计算各种绩效指标
    
    # 夏普比率：衡量风险调整后的收益
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    
    # 收益率分析
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    
    # 回撤分析
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    
    # 交易统计
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # ----- 6. 设置仓位管理器 -----
    # PercentSizer: 按百分比分配仓位
    # percents=80 表示每次用 80% 的资金买入
    cerebro.addsizer(bt.sizers.PercentSizer, percents=80)
    
    # ----- 7. 运行回测 -----
    print('=' * 50)
    print('Backtrader AAPL 10年回测')
    print('=' * 50)
    print(f'初始资金: ${cerebro.broker.getvalue():,.2f}')
    
    # cerebro.run() 会执行整个回测
    # 返回一个列表，包含所有策略的结果
    results = cerebro.run()
    
    # 获取回测结束后的账户资金
    final_value = cerebro.broker.getvalue()
    print(f'最终资金: ${final_value:,.2f}')
    print(f'总收益: ${final_value - 100000:,.2f}')
    print(f'总收益率: {(final_value / 100000 - 1) * 100:.2f}%')
    
    # ----- 8. 输出分析结果 -----
    strat = results[0]  # 获取策略结果
    
    print('\n' + '=' * 50)
    print('分析指标')
    print('=' * 50)
    
    # 夏普比率 (Sharpe Ratio)
    # > 1: 一般
    # > 2: 较好
    # > 3: 优秀
    sharpe = strat.analyzers.sharpe.get_analysis()
    if sharpe['sharperatio']:
        print(f"夏普比率: {sharpe['sharperatio']:.2f}")
    
    # 年化收益率
    returns = strat.analyzers.returns.get_analysis()
    print(f"年化收益率: {returns['rnorm100']:.2f}%")
    
    # 最大回撤 (Maximum Drawdown)
    # 历史上账户从最高点到最低点的最大跌幅
    dd = strat.analyzers.drawdown.get_analysis()
    print(f"最大回撤: {dd['max']['drawdown']:.2f}%")
    
    # 交易统计
    trades = strat.analyzers.trades.get_analysis()
    try:
        total_trades = trades.total.total
    except:
        total_trades = 0
    try:
        won_trades = trades.total.won
    except:
        won_trades = 0
    try:
        lost_trades = trades.total.lost
    except:
        lost_trades = 0
    
    print(f"\n交易统计:")
    print(f"  总交易数: {total_trades}")
    print(f"  盈利交易: {won_trades}")
    print(f"  亏损交易: {lost_trades}")
    if won_trades > 0 and total_trades > 0:
        print(f"  胜率: {won_trades / total_trades * 100:.1f}%")
    
    # ----- 9. 绘图 -----
    print('\n正在生成图表...')
    
    # 将 pandas 日期转换为 matplotlib 日期数字
    dates = pd.to_datetime(plot_data.index).tz_localize(None)
    dates_num = mdates.date2num(dates)
    
    # 创建图表：2行1列
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), gridspec_kw={'height_ratios': [3, 1]})
    
    # ===== 上图：价格和均线 =====
    ax1 = axes[0]
    
    # 绘制收盘价曲线
    ax1.plot(dates_num, plot_data['Close'], label='AAPL Price', linewidth=1, alpha=0.8)
    
    # 计算并绘制移动平均线
    # rolling(window=20).mean() 计算20日简单移动平均
    sma20 = plot_data['Close'].rolling(window=20).mean()
    sma50 = plot_data['Close'].rolling(window=50).mean()
    ax1.plot(dates_num, sma20, label='SMA 20', linewidth=1, alpha=0.7)
    ax1.plot(dates_num, sma50, label='SMA 50', linewidth=1, alpha=0.7)
    
    # 标记买卖点
    buy_signals = []  # 存储买入点的 (日期, 价格)
    sell_signals = [] # 存储卖出点的 (日期, 价格)
    
    # 遍历所有交易日，检测均线交叉
    for i in range(len(plot_data)):
        date_num = dates_num[i]
        price = plot_data['Close'].iloc[i]
        
        # 金叉买入信号：当前快线 > 慢线，前一天快线 <= 慢线
        if i >= 20 and i < len(plot_data) - 1:
            if sma20.iloc[i] > sma50.iloc[i] and sma20.iloc[i-1] <= sma50.iloc[i-1]:
                buy_signals.append((date_num, price))
        
        # 死叉卖出信号：当前快线 < 慢线，前一天快线 >= 慢线
        if i >= 20 and i < len(plot_data) - 1:
            if sma20.iloc[i] < sma50.iloc[i] and sma20.iloc[i-1] >= sma50.iloc[i-1]:
                sell_signals.append((date_num, price))
    
    # 绘制买入点（绿色三角）
    if buy_signals:
        dates_b, prices_b = zip(*buy_signals)
        ax1.scatter(dates_b, prices_b, marker='^', color='green', s=100, label='Buy', zorder=5)
    
    # 绘制卖出点（红色三角）
    if sell_signals:
        dates_s, prices_s = zip(*sell_signals)
        ax1.scatter(dates_s, prices_s, marker='v', color='red', s=100, label='Sell', zorder=5)
    
    # 图表设置
    ax1.set_title('AAPL 10-Year Backtest - Buy/Sell Signals (2016-2026)', fontsize=14)
    ax1.set_ylabel('Price ($)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    
    # ===== 下图：资金曲线 =====
    ax2 = axes[1]
    
    # 模拟资金变化
    initial_cash = 100000
    portfolio_values = [initial_cash]
    
    # 假设 80% 仓位，每天根据股价变化计算资金
    for i in range(1, len(plot_data)):
        prev_val = portfolio_values[-1]
        price_change = plot_data['Close'].iloc[i] / plot_data['Close'].iloc[i-1]
        # 80% 仓位：资金变化 = 持仓比例 * 股价变化
        new_val = prev_val * (1 + 0.8 * (price_change - 1))
        portfolio_values.append(new_val)
    
    # 绘制资金曲线
    ax2.plot(dates_num, portfolio_values, color='blue', linewidth=1)
    
    # 绘制初始资金线
    ax2.axhline(y=initial_cash, color='gray', linestyle='--', alpha=0.5)
    
    # 填充盈利区域（绿色）和亏损区域（红色）
    ax2.fill_between(dates_num, portfolio_values, initial_cash, 
                     where=[v > initial_cash for v in portfolio_values], 
                     color='green', alpha=0.3, interpolate=True)
    ax2.fill_between(dates_num, portfolio_values, initial_cash, 
                     where=[v < initial_cash for v in portfolio_values], 
                     color='red', alpha=0.3, interpolate=True)
    
    ax2.set_title('Portfolio Value', fontsize=12)
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Value ($)')
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    
    # 保存图表
    plt.tight_layout()
    plt.savefig('/home/lu/backtrader_aapl_chart.png', dpi=150, bbox_inches='tight')
    print('图表已保存到: /home/lu/backtrader_aapl_chart.png')
    plt.close()


# ==================== 程序入口 ====================
if __name__ == '__main__':
    run_backtest()
