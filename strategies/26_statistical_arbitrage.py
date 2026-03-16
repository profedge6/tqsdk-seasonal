#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
26 — 统计套利策略
Statistical Arbitrage Strategy

策略逻辑：
- 基于历史价差均值回归的统计套利策略
- 交易品种对：螺纹钢-热卷、铝-锌、铜-铝、焦煤-焦炭
- 使用协整关系检测品种对，z-score判断入场时机
- 布林带辅助判断极端偏离

作者: profedge6
更新日期: 2026-03-16
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tqsdk import TqApi, TqAuth, BacktestFuture, TqSim
from collections import defaultdict
import json
import os

# ========== 策略参数 ==========
class Config:
    # 交易对配置 (标的1, 标的2, 产业链关系)
    TRADING_PAIRS = [
        ("RB", "HC", "螺纹钢-热卷（建材产业链）"),
        ("AL", "ZN", "铝-锌（有色金属）"),
        ("CU", "AL", "铜-铝（有色金属）"),
        ("J", "JM", "焦煤-焦炭（黑色系产业链"),
        ("RU", "NR", "橡胶-20号胶（橡胶制品）"),
    ]
    
    # 套利参数
    LOOKBACK_PERIOD = 60           # 历史数据周期（交易日）
    Z_SCORE_ENTRY = 1.8            # 入场z-score阈值
    Z_SCORE_EXIT = 0.3             # 出场z-score阈值
    Z_SCORE_STOP = 2.5             # 止损z-score阈值
    
    # 布林带参数
    BOLLINGER_PERIOD = 20          # 布林带周期
    BOLLINGER_STD = 2              # 标准差倍数
    
    # 持仓参数
    POSITION_PER_PAIR = 1          # 每对合约开仓手数
    
    # 风控参数
    MAX_HOLD_DAYS = 15             # 最大持仓天数
    CORRELATION_THRESHOLD = 0.6   # 最小相关系数


# ========== 统计套利类 ==========
class StatisticalArbitrage:
    def __init__(self, api):
        self.api = api
        self.config = Config()
        self.positions = {}         # 当前持仓 {(symbol1, symbol2): direction}
        self.position_prices = {}  # 开仓价格 {(symbol1, symbol2): (price1, price2)}
        self.position_dates = {}   # 开仓日期
        self.spread_history = {}    # 价差历史数据
        
    def get_contract_data(self, symbol, days=60):
        """获取合约数据"""
        try:
            main_contract = f"KQ.m@{symbol}"
            kline = self.api.get_kline_serial(main_contract, duration_day=1, data_length=days)
            
            if kline is None or len(kline) == 0:
                return None
                
            return kline["close"].values
        except Exception as e:
            print(f"获取 {symbol} 数据失败: {e}")
            return None
    
    def calculate_spread(self, price1, price2):
        """计算价差（标准化）"""
        # 使用价格比率作为价差
        if price2 == 0:
            return 0
        return price1 / price2
    
    def calculate_correlation(self, prices1, prices2):
        """计算两品种的相关系数"""
        if len(prices1) < 20 or len(prices2) < 20:
            return 0
        
        min_len = min(len(prices1), len(prices2))
        p1 = prices1[-min_len:]
        p2 = prices2[-min_len:]
        
        return np.corrcoef(p1, p2)[0, 1]
    
    def calculate_z_score(self, spread, history):
        """计算z-score"""
        if len(history) < 10:
            return 0
        
        mean = np.mean(history)
        std = np.std(history)
        
        if std == 0:
            return 0
        
        return (spread - mean) / std
    
    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """计算布林带"""
        if len(prices) < period:
            return None, None, None
        
        recent_prices = prices[-period:]
        ma = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        upper = ma + std_dev * std
        lower = ma - std_dev * std
        
        return upper, ma, lower
    
    def check_cointegration(self, prices1, prices2):
        """简单的协整检验（简化版）"""
        if len(prices1) < 30 or len(prices2) < 30:
            return False
        
        min_len = min(len(prices1), len(prices2))
        p1 = prices1[-min_len:]
        p2 = prices2[-min_len:]
        
        # 计算价格比率
        ratios = p1 / p2
        
        # 检查比率的稳定性（标准差/均值 < 0.3 表示相对稳定）
        cv = np.std(ratios) / np.mean(ratios)
        
        return cv < 0.3
    
    def generate_signals(self):
        """生成交易信号"""
        signals = []
        
        for symbol1, symbol2, relation in self.config.TRADING_PAIRS:
            # 获取数据
            prices1 = self.get_contract_data(symbol1, self.config.LOOKBACK_PERIOD)
            prices2 = self.get_contract_data(symbol2, self.config.LOOKBACK_PERIOD)
            
            if prices1 is None or prices2 is None:
                continue
            
            # 检查相关性
            correlation = self.calculate_correlation(prices1, prices2)
            if correlation < self.config.CORRELATION_THRESHOLD:
                continue
            
            # 计算当前价差
            current_spread = self.calculate_spread(prices1[-1], prices2[-1])
            
            # 计算历史价差序列
            spread_history = []
            for i in range(20, min(len(prices1), len(prices2))):
                spread_history.append(self.calculate_spread(prices1[i], prices2[i]))
            
            # 计算z-score
            z_score = self.calculate_z_score(current_spread, spread_history)
            
            # 布林带
            upper, ma, lower = self.calculate_bollinger_bands(
                np.array(spread_history), 
                self.config.BOLLINGER_PERIOD, 
                self.config.BOLLINGER_STD
            )
            
            # 生成信号
            if z_score > self.config.Z_SCORE_ENTRY:
                # 价差偏高，做空价差（卖symbol1，买symbol2）
                signals.append({
                    "pair": (symbol1, symbol2),
                    "relation": relation,
                    "direction": -1,  # 卖symbol1，买symbol2
                    "z_score": z_score,
                    "reason": f"z-score={z_score:.2f} > {self.config.Z_SCORE_ENTRY}",
                })
            elif z_score < -self.config.Z_SCORE_ENTRY:
                # 价差偏低，做多价差（买symbol1，卖symbol2）
                signals.append({
                    "pair": (symbol1, symbol2),
                    "relation": relation,
                    "direction": 1,  # 买symbol1，卖symbol2
                    "z_score": z_score,
                    "reason": f"z-score={z_score:.2f} < -{self.config.Z_SCORE_ENTRY}",
                })
        
        return signals
    
    def check_exit_signals(self, pair):
        """检查出场信号"""
        if pair not in self.positions:
            return False
        
        symbol1, symbol2 = pair
        
        # 获取最新数据
        prices1 = self.get_contract_data(symbol1, self.config.LOOKBACK_PERIOD)
        prices2 = self.get_contract_data(symbol2, self.config.LOOKBACK_PERIOD)
        
        if prices1 is None or prices2 is None:
            return False
        
        # 计算当前价差
        current_spread = self.calculate_spread(prices1[-1], prices2[-1])
        
        # 计算历史价差
        spread_history = []
        for i in range(20, min(len(prices1), len(prices2))):
            spread_history.append(self.calculate_spread(prices1[i], prices2[i]))
        
        z_score = self.calculate_z_score(current_spread, spread_history)
        
        # 出场条件
        # 1. z-score 回归到阈值内
        if abs(z_score) < self.config.Z_SCORE_EXIT:
            return True, f"z-score回归: {z_score:.2f}"
        
        # 2. 止损
        if abs(z_score) > self.config.Z_SCORE_STOP:
            return True, f"止损: z-score={z_score:.2f}"
        
        # 3. 持仓过期
        if pair in self.position_dates:
            hold_days = (datetime.now() - self.position_dates[pair]).days
            if hold_days >= self.config.MAX_HOLD_DAYS:
                return True, f"持仓到期: {hold_days}天"
        
        return False, ""
    
    def open_position(self, pair, direction):
        """开仓"""
        symbol1, symbol2 = pair
        
        try:
            contract1 = f"KQ.m@{symbol1}"
            contract2 = f"KQ.m@{symbol2}"
            
            quote1 = self.api.get_quote(contract1)
            quote2 = self.api.get_quote(contract2)
            
            price1 = quote1.last_price
            price2 = quote2.last_price
            
            if direction > 0:
                # 做多价差：买symbol1，卖symbol2
                self.api.insert_order(symbol=contract1, direction="BUY", offset="OPEN", volume=self.config.POSITION_PER_PAIR)
                self.api.insert_order(symbol=contract2, direction="SELL", offset="OPEN", volume=self.config.POSITION_PER_PAIR)
                print(f"{symbol1}-{symbol2} 做多价差 @ {price1:.2f}/{price2:.2f}")
            else:
                # 做空价差：卖symbol1，买symbol2
                self.api.insert_order(symbol=contract1, direction="SELL", offset="OPEN", volume=self.config.POSITION_PER_PAIR)
                self.api.insert_order(symbol=contract2, direction="BUY", offset="OPEN", volume=self.config.POSITION_PER_PAIR)
                print(f"{symbol1}-{symbol2} 做空价差 @ {price1:.2f}/{price2:.2f}")
            
            self.positions[pair] = direction
            self.position_prices[pair] = (price1, price2)
            self.position_dates[pair] = datetime.now()
            
        except Exception as e:
            print(f"{symbol1}-{symbol2} 开仓失败: {e}")
    
    def close_position(self, pair):
        """平仓"""
        if pair not in self.positions:
            return
        
        symbol1, symbol2 = pair
        direction = self.positions[pair]
        
        try:
            contract1 = f"KQ.m@{symbol1}"
            contract2 = f"KQ.m@{symbol2}"
            
            quote1 = self.api.get_quote(contract1)
            quote2 = self.api.get_quote(contract2)
            
            price1 = quote1.last_price
            price2 = quote2.last_price
            
            if direction > 0:
                # 平多价差
                self.api.insert_order(symbol=contract1, direction="SELL", offset="CLOSE", volume=self.config.POSITION_PER_PAIR)
                self.api.insert_order(symbol=contract2, direction="BUY", offset="CLOSE", volume=self.config.POSITION_PER_PAIR)
            else:
                # 平空价差
                self.api.insert_order(symbol=contract1, direction="BUY", offset="CLOSE", volume=self.config.POSITION_PER_PAIR)
                self.api.insert_order(symbol=contract2, direction="SELL", offset="CLOSE", volume=self.config.POSITION_PER_PAIR)
            
            print(f"{symbol1}-{symbol2} 平仓 @ {price1:.2f}/{price2:.2f}")
            
            del self.positions[pair]
            del self.position_prices[pair]
            del self.position_dates[pair]
            
        except Exception as e:
            print(f"{symbol1}-{symbol2} 平仓失败: {e}")
    
    def run(self):
        """主循环"""
        print("=" * 50)
        print("统计套利策略启动")
        print("=" * 50)
        
        while True:
            try:
                # 检查现有持仓的出场信号
                for pair in list(self.positions.keys()):
                    should_exit, reason = self.check_exit_signals(pair)
                    if should_exit:
                        print(f"{pair[0]}-{pair[1]} 出场: {reason}")
                        self.close_position(pair)
                
                # 生成新信号
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 扫描套利机会...")
                signals = self.generate_signals()
                
                # 执行信号
                for signal in signals:
                    pair = signal["pair"]
                    direction = signal["direction"]
                    
                    # 避免重复开仓
                    if pair in self.positions:
                        # 如果方向相同，跳过
                        if self.positions[pair] == direction:
                            continue
                        # 如果方向相反，平仓后反向开仓
                        self.close_position(pair)
                    
                    # 检查是否已有太多持仓
                    if len(self.positions) >= 3:
                        break
                    
                    print(f"信号: {pair[0]}-{pair[1]} {signal['reason']}")
                    self.open_position(pair, direction)
                
                self.api.wait_update(3600)  # 每小时更新一次
                
            except KeyboardInterrupt:
                print("\n策略停止")
                break
            except Exception as e:
                print(f"运行错误: {e}")
                self.api.wait_update(60)


# ========== 回测/实盘入口 ==========
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="统计套利策略")
    parser.add_argument("--mode", choices=["backtest", "sim", "live"], default="backtest", help="运行模式")
    parser.add_argument("--username", type=str, default="", help="天勤用户名")
    parser.add_argument("--password", type=str, default="", help="天勤密码")
    args = parser.parse_args()
    
    if args.mode == "backtest":
        # 回测模式
        from datetime import datetime, timedelta
        end_date = datetime(2026, 3, 1)
        start_date = datetime(2025, 3, 1)
        
        api = TqApi(backtest=BacktestFuture(start_date=start_date, end_date=end_date))
        strategy = StatisticalArbitrage(api)
        strategy.run()
        
    elif args.mode == "sim":
        # 模拟盘模式
        api = TqApi(TqSim())
        strategy = StatisticalArbitrage(api)
        strategy.run()
        
    else:
        # 实盘模式
        if not args.username or not args.password:
            print("实盘模式需要提供用户名和密码")
            exit(1)
        
        api = TqApi(TqAuth(args.username, args.password))
        strategy = StatisticalArbitrage(api)
        strategy.run()
