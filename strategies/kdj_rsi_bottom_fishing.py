"""
KDJ+RSI 抄底策略 - 趋势反转型量化策略

【策略原理】
在超卖区域（低位）寻找买入机会，结合多个指标进行综合判断：
- KDJ超卖金叉：判断短期超卖后的反弹信号
- RSI双重确认：RSI6看短期，RSI14确认趋势
- 底背离检测：股价创新低但RSI未创新低，预示底部信号
- 成交量萎缩：辅助判断抛压减轻

【指标参数】
- KDJ: (9, 3, 3) 标准参数
- RSI: RSI6(短期) + RSI14(趋势确认)
- 成交量均线: 20日

【建仓规则】
- 首次建仓: 30%
- RSI6突破40: +20% (累计50%)
- KDJ金叉且J>50: +20% (累计70%上限)

【止盈规则】
- 第一批: RSI6>75 OR KDJ死叉(J>80后下穿) OR 盈利15% → 卖50%
- 第二批: 剩余50%再次触发任一条件 → 清仓

【止损规则】
- 亏损8%无条件止损

【风控规则】
- 单日最大亏损: 3%
- 单月最大亏损: 10%
- 连续止损3次: 暂停3天
- 连续亏损20个交易日: 重置风控状态，重新开始交易
"""

import backtrader as bt
from collections import deque
from datetime import datetime, timedelta

STRATEGY_NAME = "KDJ+RSI 抄底策略"
STRATEGY_DESCRIPTION = "KDJ超卖金叉 + RSI双重确认 + 底背离检测"


class KDJRSIBottomFishing(bt.Strategy):
    """
    KDJ+RSI 抄底策略
    
    结合随机指标(KDJ)和相对强弱指数(RSI)进行超卖区域的趋势反转交易。
    策略设计用于在市场超卖时买入，目标捕捉反弹行情。
    """
    
    params = (
        # ===== KDJ 参数 =====
        ("kdj_period", 9),       # KDJ平滑周期
        ("kdj_fastk", 3),         # KDJ快速K值平滑
        ("kdj_slowk", 3),        # KDJ慢速K值平滑
        
        # ===== RSI 参数 =====
        ("rsi6_period", 6),       # RSI短期周期
        ("rsi14_period", 14),     # RSI长期周期
        
        # ===== 成交量参数 =====
        ("volume_ma_period", 20),  # 成交量均线周期
        
        # ===== 止损止盈参数 =====
        ("stop_loss", 0.08),       # 止损比例 8%
        ("take_profit", 0.15),     # 止盈比例 15%
        ("rsi6_take_profit", 75),  # RSI6止盈阈值
        ("kdj_j_overbought", 80),  # KDJ J值超买阈值
        
        # ===== 加仓参数 =====
        ("rsi6_add_threshold", 40),  # RSI6加仓阈值
        ("kdj_j_add_threshold", 50),  # KDJ J加仓阈值
        
        # ===== 底背离参数 =====
        ("div_lookback", 20),      # 底背离回看周期
        
        # ===== 移动止盈 =====
        ("trailing_stop", 0.05),   # 移动止盈回撤比例
        
        # ===== 风控重置 =====
        ("loss_reset_days", 20),    # 连续亏损超过此天数后重置风控状态
    )
    
    def __init__(self):
        """
        策略初始化
        
        初始化所有指标、状态变量和历史数据缓冲区。
        """
        # ===== 订单状态跟踪 =====
        self.order = None
        
        # ===== 持仓相关状态 =====
        self.position_pct = 0        # 当前持仓百分比
        self.entry_price = 0        # 建仓价格
        self.highest_price = 0      # 建仓后最高价（用于移动止盈）
        
        # ===== 分批止盈相关 =====
        self.remaining_position = 0  # 剩余持仓（用于跟踪已止盈后的持仓）
        self.first_profit_taken = False  # 第一批止盈是否已完成
        
        # ===== 连续止损跟踪 =====
        self.consecutive_losses = 0  # 连续止损次数
        self.pause_until = None      # 暂停交易截止时间
        
        # ===== 风控相关 =====
        self.daily_loss = 0         # 当日亏损金额
        self.monthly_loss = 0       # 当月亏损金额
        self.month_start_date = None  # 当月开始日期
        self.last_trade_date = None  # 上次交易日期
        self.daily_pnl = 0          # 当日盈亏
        self.days_since_profit = 0   # 上次盈利以来的交易日计数
        self.trading_days = 0        # 总交易天数计数
        
        # ===== 底背离检测历史数据 =====
        self.price_history = deque(maxlen=self.p.div_lookback + 1)
        self.rsi6_history = deque(maxlen=self.p.div_lookback + 1)
        
        # ===== 初始化 KDJ 指标 =====
        # KDJ指标包含K、D、J三条线
        # K和D线范围0-100，J线可以超过这个范围
        # Backtrader的Stochastic参数: period, period_dfast(=K平滑), period_dslow(=D平滑)
        self.kdj = bt.indicators.Stochastic(
            self.data,
            period=self.p.kdj_period,
            period_dfast=self.p.kdj_fastk,
            period_dslow=self.p.kdj_slowk,
        )
        
        # 手动计算J线: J = 3*K - 2*D
        self.kdj.j = 3 * self.kdj.lines.percK - 2 * self.kdj.lines.percD
        
        # ===== 初始化 RSI 指标 =====
        # RSI6: 短期RSI，对价格变化更敏感
        # RSI14: 长期RSI，趋势确认更稳定
        self.rsi6 = bt.indicators.RSI(
            self.data.close,
            period=self.p.rsi6_period
        )
        self.rsi14 = bt.indicators.RSI(
            self.data.close,
            period=self.p.rsi14_period
        )
        
        # ===== 初始化成交量均线 =====
        self.volume_ma = bt.indicators.SMA(
            self.data.volume,
            period=self.p.volume_ma_period
        )
        
        # ===== 初始化交叉指标 =====
        # K线上穿D线（金叉/死叉）
        self.kd_cross = bt.indicators.CrossOver(
            self.kdj.lines.percK,
            self.kdj.lines.percD
        )
        # J线下穿K线（用于KDJ死叉检测）
        self.jk_cross = bt.indicators.CrossOver(
            self.kdj.j,
            self.kdj.lines.percK
        )
    
    def log(self, txt, dt=None):
        """
        日志输出
        
        用于调试和跟踪策略执行过程。
        
        参数:
            txt: 日志文本
            dt: 日期时间，默认为当前K线日期
        """
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} - {txt}')
    
    def notify_order(self, order):
        """
        订单状态通知
        
        处理订单完成、取消、被拒等情况。
        
        参数:
            order: 订单对象
        """
        # 等待提交的订单不处理
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        # 订单已完成
        if order.status == order.Completed:
            # 更新持仓价格
            if order.isbuy():
                self.entry_price = order.executed.price
                self.highest_price = self.entry_price
                self.last_trade_date = self.data.datetime.date(0)
            
            # 更新最高价（如果刚卖出一部分）
            current_price = self.data.close[0]
            if current_price > self.highest_price:
                self.highest_price = current_price
            
            self.order = None
        
        # 订单取消、保证金不足或拒绝
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'订单失败: {[order.Canceled, order.Margin, order.Rejected][order.status - 2]}')
            self.order = None
    
    def notify_trade(self, trade):
        """
        交易完成通知
        
        当一笔交易完全平仓时调用，用于更新风控统计。
        
        参数:
            trade: 交易对象
        """
        # 交易未结束
        if trade.isclosed == 0:
            return
        
        # 获取交易盈亏
        pnl = trade.pnl
        
        # 更新连续止损计数
        if pnl < 0:
            self.consecutive_losses += 1
            self.days_since_profit += 1  # 亏损交易日计数+1
            # 连续止损3次，暂停3天
            if self.consecutive_losses >= 3:
                self.pause_until = self.data.datetime.date(0) + timedelta(days=3)
                self.log(f'连续止损3次，暂停交易至 {self.pause_until}')
        else:
            self.consecutive_losses = 0
            self.days_since_profit = 0  # 盈利后重置计数
        
        # 更新当月亏损
        if self.month_start_date is None:
            self.month_start_date = self.data.datetime.date(0)
        
        current_date = self.data.datetime.date(0)
        if current_date.month != self.month_start_date.month:
            # 新月份，重置
            self.monthly_loss = 0
            self.month_start_date = current_date
        else:
            if pnl < 0:
                self.monthly_loss += abs(pnl)
        
        # 更新当日盈亏
        self.daily_pnl += pnl
        
        # 重置最高价（持仓改变后需要重新计算）
        if self.position.size > 0:
            self.highest_price = max(self.highest_price, self.data.close[0])
        else:
            self.highest_price = 0
    
    def is_paused(self):
        """
        检查是否处于暂停交易状态
        
        返回:
            bool: 如果暂停返回True，否则返回False
        """
        if self.pause_until is None:
            return False
        
        current_date = self.data.datetime.date(0)
        if current_date >= self.pause_until:
            # 暂停期结束，恢复交易
            self.pause_until = None
            self.log('暂停期结束，恢复交易')
            return False
        
        return True
    
    def check_risk_management(self):
        """
        风控检查
        
        检查是否允许进行新的交易。
        
        返回:
            bool: 如果允许交易返回True，否则返回False
        """
        # 交易日计数+1
        self.trading_days += 1
        
        # 检查连续亏损重置：超过指定交易日无盈利，重置所有风控状态
        if self.days_since_profit >= self.params.loss_reset_days:
            if self.consecutive_losses > 0 or self.is_paused():
                self.log(f'连续亏损{self.days_since_profit}个交易日后，重置所有风控状态')
                self.consecutive_losses = 0
                self.pause_until = None
                self.daily_loss = 0
                self.monthly_loss = 0  # 同时重置月度亏损统计
                self.days_since_profit = 0
                self.log('风控状态已重置，恢复正常交易')
        
        # 检查连续止损暂停
        if self.is_paused():
            return False
        
        # 检查单月亏损限制（10%）
        account_value = self.broker.getvalue()
        monthly_loss_threshold = account_value * 0.10
        if self.monthly_loss >= monthly_loss_threshold:
            self.log(f'单月亏损达到 {self.monthly_loss:.2f}，超过阈值 {monthly_loss_threshold:.2f}，暂停交易')
            return False
        
        return True
    
    def check_buy_signals(self):
        """
        检查买入信号
        
        检测各种买入条件是否满足。
        
        返回:
            dict: {
                'kdj_golden_cross': bool,  # KDJ超卖金叉
                'rsi_oversold': bool,      # RSI超卖反弹
                'rsi_divergence': bool,    # RSI底背离
                'volume_shrink': bool      # 成交量萎缩
            }
        """
        signals = {
            'kdj_golden_cross': False,
            'rsi_oversold': False,
            'rsi_divergence': False,
            'volume_shrink': False
        }
        
        # ===== 信号1: KDJ超卖金叉 =====
        # 条件: J<20 且 K线上穿D线
        if (self.kdj.j[-1] < 20 and self.kd_cross[0] > 0):
            signals['kdj_golden_cross'] = True
        
        # ===== 信号2: RSI双重超卖反弹 =====
        # 条件: RSI6<25 且 RSI14<40
        if (self.rsi6[0] < 25 and self.rsi14[0] < 40):
            signals['rsi_oversold'] = True
        
        # ===== 信号3: RSI底背离 =====
        # 条件: 股价创20日新低 且 RSI6未创新低
        if len(self.price_history) >= self.p.div_lookback:
            # 当前价格
            current_price = self.data.close[0]
            current_rsi6 = self.rsi6[0]
            
            # 20日内的最低价
            price_low_20 = min(list(self.price_history))
            rsi6_low_20 = min(list(self.rsi6_history))
            
            # 检测底背离: 价格新低但RSI未新低
            if (current_price < price_low_20 and 
                current_rsi6 > rsi6_low_20):
                signals['rsi_divergence'] = True
        
        # ===== 信号4: 成交量萎缩 =====
        # 条件: 当前成交量 < 20日均量的40%
        if self.volume_ma[0] > 0:
            volume_ratio = self.data.volume[0] / self.volume_ma[0]
            if volume_ratio < 0.4:
                signals['volume_shrink'] = True
        
        return signals
    
    def check_add_position_signals(self):
        """
        检查加仓信号
        
        返回:
            dict: {
                'rsi6_break40': bool,       # RSI6突破40
                'kdj_golden_j50': bool       # KDJ金叉且J>50
            }
        """
        signals = {
            'rsi6_break40': False,
            'kdj_golden_j50': False
        }
        
        # ===== 加仓信号1: RSI6突破40 =====
        # 条件: 前一根RSI6<=40 且 当前RSI6>40
        if (self.rsi6[-1] <= self.p.rsi6_add_threshold and 
            self.rsi6[0] > self.p.rsi6_add_threshold):
            signals['rsi6_break40'] = True
        
        # ===== 加仓信号2: KDJ金叉且J>50 =====
        # 条件: K线上穿D线 且 J>50
        if self.kd_cross[0] > 0 and self.kdj.j[0] > self.p.kdj_j_add_threshold:
            signals['kdj_golden_j50'] = True
        
        return signals
    
    def check_sell_signals(self):
        """
        检查卖出信号
        
        返回:
            dict: {
                'rsi6_overbought': bool,  # RSI6>75
                'kdj_death_cross': bool,  # KDJ死叉(J>80后下穿)
                'profit_target': bool,    # 盈利15%
                'stop_loss': bool         # 亏损8%
            }
        """
        signals = {
            'rsi6_overbought': False,
            'kdj_death_cross': False,
            'profit_target': False,
            'stop_loss': False
        }
        
        current_price = self.data.close[0]
        
        # ===== 止损检查（无条件优先）=====
        if self.entry_price > 0:
            loss_ratio = (self.entry_price - current_price) / self.entry_price
            if loss_ratio >= self.params.stop_loss:
                signals['stop_loss'] = True
                return signals  # 止损优先，直接返回
        
        # ===== 止盈检查 =====
        if self.entry_price > 0:
            profit_ratio = (current_price - self.entry_price) / self.entry_price
            
            # 止盈条件1: RSI6>75
            if self.rsi6[0] > self.params.rsi6_take_profit:
                signals['rsi6_overbought'] = True
            
            # 止盈条件2: KDJ死叉（J>80后下穿）
            # 需要确认J线之前站上过80
            if (self.kdj.j[-1] > self.params.kdj_j_overbought and 
                self.jk_cross[0] < 0):
                signals['kdj_death_cross'] = True
            
            # 止盈条件3: 盈利15%
            if profit_ratio >= self.params.take_profit:
                signals['profit_target'] = True
        
        return signals
    
    def check_trailing_stop(self):
        """
        检查移动止盈
        
        适用于剩余50%持仓的回撤保护。
        
        返回:
            bool: 如果触发移动止盈返回True
        """
        if self.remaining_position > 0 and self.highest_price > 0:
            current_price = self.data.close[0]
            drawdown = (self.highest_price - current_price) / self.highest_price
            if drawdown >= self.params.trailing_stop:
                return True
        return False
    
    def next(self):
        """
        主循环 - 每个K线执行一次
        
        策略的核心逻辑，按顺序执行：
        1. 更新历史数据
        2. 风控检查
        3. 卖出逻辑（止损、止盈）
        4. 加仓逻辑
        5. 买入逻辑
        """
        # 如果有待处理订单，跳过
        if self.order:
            return
        
        # ===== 更新历史数据（用于底背离检测）=====
        self.price_history.append(self.data.close[0])
        self.rsi6_history.append(self.rsi6[0])
        
        # ===== 风控检查 =====
        if not self.check_risk_management():
            return
        
        # ===== 检查卖出信号 =====
        sell_signals = self.check_sell_signals()
        
        # 止损: 全部卖出
        if sell_signals['stop_loss']:
            self.log(f'止损出局! 亏损比例: {(self.entry_price - self.data.close[0]) / self.entry_price * 100:.2f}%')
            self.order = self.close()
            self.position_pct = 0
            self.remaining_position = 0
            self.first_profit_taken = False
            return
        
        # ===== 止盈逻辑（分批）=====
        if self.position.size > 0:
            any_profit_signal = (sell_signals['rsi6_overbought'] or 
                                sell_signals['kdj_death_cross'] or 
                                sell_signals['profit_target'])
            
            # 第一批止盈: 满足条件且未止盈过
            if any_profit_signal and not self.first_profit_taken:
                self.log(f'止盈第一批(50%)! 信号: RSI6={self.rsi6[0]:.2f}, KDJ_J={self.kdj.j[0]:.2f}')
                self.order = self.sell(size=self.position.size // 2)
                self.first_profit_taken = True
                self.remaining_position = self.position.size
                return
            
            # 第二批止盈: 剩余持仓再次触发条件
            if any_profit_signal and self.first_profit_taken:
                self.log(f'止盈第二批(清仓)! 信号: RSI6={self.rsi6[0]:.2f}, KDJ_J={self.kdj.j[0]:.2f}')
                self.order = self.close()
                self.position_pct = 0
                self.remaining_position = 0
                self.first_profit_taken = False
                return
            
            # 移动止盈检查（针对剩余50%）
            if self.check_trailing_stop():
                self.log(f'移动止盈出局! 回撤: {(self.highest_price - self.data.close[0]) / self.highest_price * 100:.2f}%')
                self.order = self.close()
                self.position_pct = 0
                self.remaining_position = 0
                self.first_profit_taken = False
                return
            
            # ===== 加仓逻辑 =====
            if self.position_pct < 70:
                add_signals = self.check_add_position_signals()
                add_size = 0
                
                # RSI6突破40: 加20%
                if add_signals['rsi6_break40']:
                    add_size += 0.20
                
                # KDJ金叉且J>50: 再加20%
                if add_signals['kdj_golden_j50']:
                    add_size += 0.20
                
                # 执行加仓
                if add_size > 0:
                    new_total_pct = min(self.position_pct + add_size, 0.70)
                    target_size = new_total_pct - self.position_pct
                    
                    self.log(f'加仓! 目标: {new_total_pct*100:.0f}%, RSI6={self.rsi6[0]:.2f}, KDJ_J={self.kdj.j[0]:.2f}')
                    self.order = self.buy(size=int(target_size * 100))  # 按合约数量
                    self.position_pct = new_total_pct
                    return
        
        # ===== 买入逻辑 =====
        if not self.position:
            buy_signals = self.check_buy_signals()
            
            # 主要条件（满足任一即可）
            main_signal = (buy_signals['kdj_golden_cross'] or 
                          buy_signals['rsi_oversold'] or 
                          buy_signals['rsi_divergence'])
            
            # 辅助条件（加分项，可选）
            assist_signal = buy_signals['volume_shrink']
            
            # 买入条件: 满足主要条件
            if main_signal:
                signal_list = []
                if buy_signals['kdj_golden_cross']:
                    signal_list.append('KDJ金叉')
                if buy_signals['rsi_oversold']:
                    signal_list.append('RSI超卖')
                if buy_signals['rsi_divergence']:
                    signal_list.append('底背离')
                if assist_signal:
                    signal_list.append('量能萎缩')
                
                self.log(f'买入信号! {"/".join(signal_list)}')
                self.order = self.buy()  # 默认买入1手
                self.position_pct = 0.30  # 首次建仓30%
                self.entry_price = self.data.close[0]
                self.highest_price = self.entry_price


# 导出策略类 - Web界面加载必需
STRATEGY_CLASS = KDJRSIBottomFishing
