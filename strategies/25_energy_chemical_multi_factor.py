#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
25 — 能源化工多因子截面策略
Energy & Chemical Multi-Factor Cross-Sectional Strategy

策略逻辑：
- 多因子模型应用于能源化工品种（原油、PTA、沥青、燃料油、甲醇、橡胶）
- 因子设计：动量 + 波动率 + 期限结构 + 供需情绪
- 持仓选择：做多得分最高的品种，做空得分最低的品种
- 调仓频率：每周或信号触发时

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
    # 合约列表 - 能源化工品种
    CONTRACTS = {
        "SC": "SC2005",      # 原油
        "TA": "TA2005",      # PTA
        "BU": "BU2006",      # 沥青
        "FU": "FU2005",      # 燃料油
        "MA": "MA2005",      # 甲醇
        "RU": "RU2005",      # 橡胶
    }
    
    # 因子权重
    FACTOR_WEIGHTS = {
        "momentum": 0.30,      # 动量因子权重
        "volatility": 0.25,    # 波动率因子权重
        "basis": 0.25,         # 期限结构因子权重
        "sentiment": 0.20,     # 供需情绪因子权重
    }
    
    # 持仓参数
    MAX_POSITIONS = 2          # 最多持仓品种数
    POSITION_PER_CONTRACT = 1  # 每个品种开仓手数
    
    # 风控参数
    STOP_LOSS_PCT = 0.025      # 止损 2.5%
    TAKE_PROFIT_PCT = 0.05     # 止盈 5%
    MAX_HOLD_DAYS = 10         # 最大持仓天数
    
    # 因子计算参数
    MOMENTUM_PERIOD = 20       # 动量周期
    VOLATILITY_PERIOD = 20     # 波动率周期
    REBALANCE_DAYS = 5         # 调仓周期（交易日）


# ========== 因子计算函数 ==========
def calculate_momentum(prices, period=20):
    """动量因子：价格变化率"""
    if len(prices) < period:
        return 0
    return (prices[-1] / prices[-period] - 1) * 100


def calculate_volatility(returns, period=20):
    """波动率因子：收益率标准差（年化）"""
    if len(returns) < period:
        return 0
    recent_returns = returns[-period:]
    volatility = np.std(recent_returns) * np.sqrt(252)
    return volatility


def calculate_basis(front_month, next_month):
    """期限结构因子：contango/backwardation"""
    if front_month is None or next_month is None or next_month == 0:
        return 0
    # Contango (远月升水) -> 市场预期上涨 -> 正分
    # Backwardation (远月贴水) -> 市场预期下跌 -> 负分
    return (next_month - front_month) / front_month * 100


def calculate_sentiment(volume, price_change, position):
    """供需情绪因子：成交量变化 + 价格趋势强度"""
    # 成交量趋势
    if len(volume) < 10:
        volume_signal = 0
    else:
        volume_trend = (volume[-1] / np.mean(volume[-10:]) - 1) * 100
        volume_signal = np.clip(volume_trend / 20, -1, 1)
    
    # 价格趋势强度
    price_signal = np.clip(price_change / 2, -1, 1)
    
    return (volume_signal + price_signal) / 2


def normalize_factor(factor_values):
    """Z-score 标准化因子"""
    values = list(factor_values.values())
    mean = np.mean(values)
    std = np.std(values)
    if std == 0:
        return {k: 0 for k in factor_values.keys()}
    return {k: (v - mean) / std for k, v in factor_values.items()}


# ========== 主策略类 ==========
class EnergyChemicalMultiFactor:
    def __init__(self, api):
        self.api = api
        self.config = Config()
        self.positions = {}           # 当前持仓
        self.position_prices = {}     # 开仓价格
        self.position_dates = {}      # 开仓日期
        self.last_rebalance = None   # 上次调仓日期
        self.factor_cache = {}       # 因子缓存
        
    def get_contract_data(self, symbol):
        """获取合约数据"""
        try:
            # 主力合约
            main_contract = f"KQ.m@{symbol}"
            kline = self.api.get_kline_serial(main_contract, duration_day=1, data_length=60)
            
            if kline is None or len(kline) == 0:
                return None
                
            return {
                "close": kline["close"].values,
                "volume": kline["volume"].values,
                "high": kline["high"].values,
                "low": kline["low"].values,
            }
        except Exception as e:
            print(f"获取 {symbol} 数据失败: {e}")
            return None
    
    def calculate_all_factors(self):
        """计算所有品种的因子得分"""
        factor_scores = {}
        
        for symbol in self.config.CONTRACTS.keys():
            data = self.get_contract_data(symbol)
            if data is None or len(data["close"]) < 30:
                continue
            
            close = data["close"]
            volume = data["volume"]
            
            # 计算收益率
            returns = np.diff(close) / close[:-1]
            
            # 1. 动量因子
            momentum = calculate_momentum(close, self.config.MOMENTUM_PERIOD)
            
            # 2. 波动率因子（低波动率得正分）
            volatility = calculate_volatility(returns, self.config.VOLATILITY_PERIOD)
            volatility_score = -volatility  # 低波动率是优势
            
            # 3. 期限结构因子
            if len(close) >= 5:
                front_month = close[-1]
                next_month = close[-5]
                basis = calculate_basis(front_month, next_month)
            else:
                basis = 0
            
            # 4. 供需情绪因子
            price_change = (close[-1] / close[-5] - 1) * 100 if len(close) >= 5 else 0
            sentiment = calculate_sentiment(volume, price_change, 0)
            
            # 标准化因子
            factor_scores[symbol] = {
                "momentum": momentum,
                "volatility": volatility_score,
                "basis": basis,
                "sentiment": sentiment,
            }
        
        return factor_scores
    
    def calculate_composite_score(self, factor_scores):
        """计算综合得分"""
        if not factor_scores:
            return {}
        
        # 标准化每个因子
        normalized = {}
        for factor_name in ["momentum", "volatility", "basis", "sentiment"]:
            values = {s: fs[factor_name] for s, fs in factor_scores.items()}
            normalized[factor_name] = normalize_factor(values)
        
        # 计算加权综合得分
        composite = {}
        for symbol in factor_scores.keys():
            score = 0
            for factor_name, weight in self.config.FACTOR_WEIGHTS.items():
                score += normalized[factor_name][symbol] * weight
            composite[symbol] = score
        
        return composite
    
    def select_positions(self, composite_scores):
        """选择持仓品种"""
        if len(composite_scores) < 2:
            return [], []
        
        sorted_symbols = sorted(composite_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 做多得分最高的
        long_symbols = [s[0] for s in sorted_symbols[:self.config.MAX_POSITIONS]]
        
        # 做空得分最低的
        short_symbols = [s[0] for s in sorted_symbols[-self.config.MAX_POSITIONS:]]
        
        return long_symbols, short_symbols
    
    def check_stop_loss_take_profit(self, symbol, current_price):
        """检查止损止盈"""
        if symbol not in self.positions or symbol not in self.position_prices:
            return False
        
        entry_price = self.position_prices[symbol]
        position = self.positions[symbol]
        
        # 计算收益率
        if position > 0:  # 多头
            pnl_pct = (current_price - entry_price) / entry_price
        else:  # 空头
            pnl_pct = (entry_price - current_price) / entry_price
        
        # 止损
        if pnl_pct <= -self.config.STOP_LOSS_PCT:
            print(f"{symbol} 触发止损: {pnl_pct*100:.2f}%")
            return True
        
        # 止盈
        if pnl_pct >= self.config.TAKE_PROFIT_PCT:
            print(f"{symbol} 触发止盈: {pnl_pct*100:.2f}%")
            return True
        
        return False
    
    def check_position_expired(self, symbol):
        """检查持仓是否过期"""
        if symbol not in self.position_dates:
            return False
        
        hold_days = (datetime.now() - self.position_dates[symbol]).days
        return hold_days >= self.config.MAX_HOLD_DAYS
    
    def rebalance(self, target_long, target_short):
        """调仓"""
        current_date = datetime.now().date()
        
        # 平掉不在目标中的持仓
        for symbol in list(self.positions.keys()):
            if symbol not in target_long and symbol not in target_short:
                self.close_position(symbol)
        
        # 开多仓
        for symbol in target_long:
            if symbol not in self.positions or self.positions.get(symbol, 0) <= 0:
                self.open_position(symbol, 1)  # 多头
        
        # 开空仓
        for symbol in target_short:
            if symbol not in self.positions or self.positions.get(symbol, 0) >= 0:
                self.open_position(symbol, -1)  # 空头
        
        self.last_rebalance = current_date
    
    def open_position(self, symbol, direction):
        """开仓"""
        contract = self.config.CONTRACTS.get(symbol)
        if contract is None:
            return
        
        try:
            main_contract = f"KQ.m@{symbol}"
            quote = self.api.get_quote(main_contract)
            current_price = quote.last_price
            
            if direction > 0:
                self.api.insert_order(symbol=main_contract, direction="BUY", offset="OPEN", volume=self.config.POSITION_PER_CONTRACT)
                print(f"{symbol} 开多仓 @ {current_price}")
            else:
                self.api.insert_order(symbol=main_contract, direction="SELL", offset="OPEN", volume=self.config.POSITION_PER_CONTRACT)
                print(f"{symbol} 开空仓 @ {current_price}")
            
            self.positions[symbol] = direction * self.config.POSITION_PER_CONTRACT
            self.position_prices[symbol] = current_price
            self.position_dates[symbol] = datetime.now()
            
        except Exception as e:
            print(f"{symbol} 开仓失败: {e}")
    
    def close_position(self, symbol):
        """平仓"""
        contract = self.config.CONTRACTS.get(symbol)
        if contract is None:
            return
        
        if symbol not in self.positions:
            return
        
        try:
            main_contract = f"KQ.m@{symbol}"
            quote = self.api.get_quote(main_contract)
            current_price = quote.last_price
            direction = self.positions[symbol]
            
            if direction > 0:
                self.api.insert_order(symbol=main_contract, direction="SELL", offset="CLOSE", volume=self.config.POSITION_PER_CONTRACT)
                print(f"{symbol} 平多仓 @ {current_price}")
            else:
                self.api.insert_order(symbol=main_contract, direction="BUY", offset="CLOSE", volume=self.config.POSITION_PER_CONTRACT)
                print(f"{symbol} 平空仓 @ {current_price}")
            
            del self.positions[symbol]
            del self.position_prices[symbol]
            del self.position_dates[symbol]
            
        except Exception as e:
            print(f"{symbol} 平仓失败: {e}")
    
    def run(self):
        """主循环"""
        print("=" * 50)
        print("能源化工多因子截面策略启动")
        print("=" * 50)
        
        while True:
            try:
                current_date = datetime.now().date()
                
                # 检查是否需要调仓
                need_rebalance = False
                if self.last_rebalance is None:
                    need_rebalance = True
                else:
                    days_since = (current_date - self.last_rebalance).days
                    if days_since >= self.config.REBALANCE_DAYS:
                        need_rebalance = True
                
                if need_rebalance:
                    print(f"\n[{current_date}] 计算因子得分...")
                    factor_scores = self.calculate_all_factors()
                    composite_scores = self.calculate_composite_score(factor_scores)
                    
                    if composite_scores:
                        long_symbols, short_symbols = self.select_positions(composite_scores)
                        print(f"做多品种: {long_symbols}")
                        print(f"做空品种: {short_symbols}")
                        self.rebalance(long_symbols, short_symbols)
                
                # 检查止损止盈和持仓过期
                for symbol in list(self.positions.keys()):
                    try:
                        main_contract = f"KQ.m@{symbol}"
                        quote = self.api.get_quote(main_contract)
                        current_price = quote.last_price
                        
                        if self.check_stop_loss_take_profit(symbol, current_price):
                            self.close_position(symbol)
                        elif self.check_position_expired(symbol):
                            print(f"{symbol} 持仓到期，平仓")
                            self.close_position(symbol)
                    except:
                        pass
                
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
    
    parser = argparse.ArgumentParser(description="能源化工多因子截面策略")
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
        strategy = EnergyChemicalMultiFactor(api)
        strategy.run()
        
    elif args.mode == "sim":
        # 模拟盘模式
        api = TqApi(TqSim())
        strategy = EnergyChemicalMultiFactor(api)
        strategy.run()
        
    else:
        # 实盘模式
        if not args.username or not args.password:
            print("实盘模式需要提供用户名和密码")
            exit(1)
        
        api = TqApi(TqAuth(args.username, args.password))
        strategy = EnergyChemicalMultiFactor(api)
        strategy.run()
