#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
跨期套利策略 - 策略24
Calendar Spread Arbitrage Strategy

策略逻辑：
- 利用同一品种不同到期月份合约的价差均值回归特性
- 当近月-远月价差偏离历史均值时，做多价差或做空价差
- 价差回归时平仓获利
- 适用于金属、能源、化工等具有明显期限结构的品种
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from tqsdk import TqApi, TqAuth, Backtest, TqSim
from tqsdk.ta import MA, STD


class CalendarSpreadArbitrage:
    """跨期套利策略"""
    
    # 交易品种配置 (symbol, near_month_code, far_month_code)
    PAIRS = [
        # 金属
        ("SHFE.cu", "cu2409", "cu2501"),   # 铜 9月-1月
        ("SHFE.al", "al2409", "al2501"),   # 铝 9月-1月
        ("SHFE.zn", "zn2409", "zn2501"),   # 锌 9月-1月
        ("SHFE.ni", "ni2409", "ni2501"),   # 镍 9月-1月
        # 能源化工
        ("SC", "sc2409", "sc2501"),        # 原油 9月-1月
        ("RU", "ru2409", "ru2501"),        # 橡胶 9月-1月
    ]
    
    # 策略参数
    LOOKBACK_PERIOD = 60      # 回看周期
    ENTRY_ZSCORE = 1.8        # 入场z-score阈值
    EXIT_ZSCORE = 0.3         # 出场z-score阈值
    STOP_LOSS = 2.5           # 止损z-score
    MAX_HOLD_DAYS = 15        # 最大持仓天数
    
    def __init__(self, api: TqApi):
        self.api = api
        self.spreads = {}     # pair -> spread series
        self.positions = {}  # pair -> position info
        self.last_update = None
        self.entry_time = {} # pair -> entry time
        
    async def initialize(self):
        """初始化策略"""
        print("初始化跨期套利策略...")
        
        for pair_name, near_code, far_code in self.PAIRS:
            try:
                # 获取两个合约的K线
                near_kline = await self.api.get_kline_serial(f"SHFE.{near_code}" if "." not in near_code else near_code, "1d", self.LOOKBACK_PERIOD)
                far_kline = await self.api.get_kline_serial(f"SHFE.{far_code}" if "." not in far_code else far_code, "1d", self.LOOKBACK_PERIOD)
                
                # 计算价差
                near_prices = near_kline['close'].tolist()
                far_prices = far_kline['close'].tolist()
                
                spreads = []
                for i in range(min(len(near_prices), len(far_prices))):
                    spread = near_prices[i] - far_prices[i]
                    spreads.append(spread)
                
                self.spreads[pair_name] = spreads
                print(f"  已加载 {pair_name} 价差数据 ({len(spreads)}条)")
                
            except Exception as e:
                print(f"  加载 {pair_name} 失败: {e}")
    
    def calculate_spread_stats(self, spreads: List[float]) -> Tuple[float, float]:
        """计算价差的均值和标准差"""
        if len(spreads) < 10:
            return 0, 1
        mean = np.mean(spreads)
        std = np.std(spreads)
        return mean, std
    
    def calculate_zscore(self, spread: float, mean: float, std: float) -> float:
        """计算z-score"""
        if std == 0:
            return 0
        return (spread - mean) / std
    
    async def get_current_spread(self, pair_name: str, near_code: str, far_code: str) -> Optional[float]:
        """获取当前价差"""
        try:
            near_symbol = f"SHFE.{near_code}" if "." not in near_code else near_code
            far_symbol = f"SHFE.{far_code}" if "." not in far_code else far_code
            
            near_quote = await self.api.get_quote(near_symbol)
            far_quote = await self.api.get_quote(far_symbol)
            
            spread = near_quote["last_price"] - far_quote["last_price"]
            return spread
        except Exception as e:
            print(f"获取当前价差失败 {pair_name}: {e}")
            return None
    
    async def check_and_trade(self):
        """检查所有交易对并执行交易"""
        current_time = datetime.now()
        
        # 每天检查一次
        if self.last_update:
            hours_since = (current_time - self.last_update).total_seconds() / 3600
            if hours_since < 4:  # 至少4小时检查一次
                return
        
        print("\n=== 跨期套利信号检查 ===")
        
        for pair_name, near_code, far_code in self.PAIRS:
            if pair_name not in self.spreads:
                continue
            
            spreads = self.spreads[pair_name]
            mean, std = self.calculate_spread_stats(spreads)
            
            current_spread = await self.get_current_spread(pair_name, near_code, far_code)
            if current_spread is None:
                continue
            
            zscore = self.calculate_zscore(current_spread, mean, std)
            print(f"{pair_name}: 价差={current_spread:.2f}, 均值={mean:.2f}, z-score={zscore:.2f}")
            
            # 检查是否需要平仓
            if pair_name in self.positions:
                await self.check_exit(pair_name, near_code, far_code, current_spread, zscore)
            else:
                # 检查是否需要开仓
                await self.check_entry(pair_name, near_code, far_code, current_spread, zscore)
            
            # 更新价差序列
            self.spreads[pair_name].append(current_spread)
            if len(self.spreads[pair_name]) > self.LOOKBACK_PERIOD:
                self.spreads[pair_name].pop(0)
        
        self.last_update = current_time
    
    async def check_entry(self, pair_name: str, near_code: str, far_code: str, 
                          spread: float, zscore: float):
        """检查入场信号"""
        # 检查持仓超时
        if pair_name in self.entry_time:
            days_held = (datetime.now() - self.entry_time[pair_name]).days
            if days_held >= self.MAX_HOLD_DAYS:
                print(f"{pair_name}: 持仓超{max_held}天，跳过入场")
                return
        
        direction = None
        
        # z-score > 1.8: 价差高于均值，做空价差（预期回归）
        if zscore > self.ENTRY_ZSCORE:
            direction = "short_spread"  # 做空价差 = 空近月，多远月
            print(f"{pair_name}: 入场信号 - 做空价差 (z={zscore:.2f})")
        
        # z-score < -1.8: 价差低于均值，做多价差（预期回归）
        elif zscore < -self.ENTRY_ZSCORE:
            direction = "long_spread"  # 做多价差 = 多近月，空远月
            print(f"{pair_name}: 入场信号 - 做多价差 (z={zscore:.2f})")
        
        if direction:
            await self.open_spread(pair_name, near_code, far_code, direction)
    
    async def check_exit(self, pair_name: str, near_code: str, far_code: str,
                        spread: float, zscore: float):
        """检查出场信号"""
        position = self.positions[pair_name]
        
        # 止损
        if abs(zscore) > self.STOP_LOSS:
            print(f"{pair_name}: 止损信号 (z={zscore:.2f})")
            await self.close_spread(pair_name, near_code, far_code)
            return
        
        # 止盈/回归出场
        if abs(zscore) < self.EXIT_ZSCORE:
            print(f"{pair_name}: 出场信号 - 价差回归 (z={zscore:.2f})")
            await self.close_spread(pair_name, near_code, far_code)
            return
        
        # 持仓超时
        if pair_name in self.entry_time:
            days_held = (datetime.now() - self.entry_time[pair_name]).days
            if days_held >= self.MAX_HOLD_DAYS:
                print(f"{pair_name}: 持仓超时强平")
                await self.close_spread(pair_name, near_code, far_code)
    
    async def open_spread(self, pair_name: str, near_code: str, far_code: str, direction: str):
        """开仓套利"""
        try:
            near_symbol = f"SHFE.{near_code}" if "." not in near_code else near_code
            far_symbol = f"SHFE.{far_code}" if "." not in far_code else far_code
            
            near_quote = await self.api.get_quote(near_symbol)
            far_quote = await self.api.get_quote(far_symbol)
            
            volume = 1  # 每次1手
            
            if direction == "short_spread":
                # 做空价差 = 空近月，多远月
                await self.api.insert_order(
                    symbol=near_symbol,
                    direction="sell",
                    offset="open",
                    volume=volume,
                    limit_price=near_quote["last_price"]
                )
                await self.api.insert_order(
                    symbol=far_symbol,
                    direction="buy",
                    offset="open",
                    volume=volume,
                    limit_price=far_quote["last_price"]
                )
            else:
                # 做多价差 = 多近月，空远月
                await self.api.insert_order(
                    symbol=near_symbol,
                    direction="buy",
                    offset="open",
                    volume=volume,
                    limit_price=near_quote["last_price"]
                )
                await self.api.insert_order(
                    symbol=far_symbol,
                    direction="sell",
                    offset="open",
                    volume=volume,
                    limit_price=far_quote["last_price"]
                )
            
            self.positions[pair_name] = {
                "direction": direction,
                "near_symbol": near_symbol,
                "far_symbol": far_symbol,
                "volume": volume
            }
            self.entry_time[pair_name] = datetime.now()
            print(f"{pair_name}: 开仓成功 - {direction}")
            
        except Exception as e:
            print(f"{pair_name}: 开仓失败 - {e}")
    
    async def close_spread(self, pair_name: str, near_code: str, far_code: str):
        """平仓套利"""
        if pair_name not in self.positions:
            return
        
        try:
            position = self.positions[pair_name]
            near_symbol = position["near_symbol"]
            far_symbol = position["far_symbol"]
            volume = position["volume"]
            direction = position["direction"]
            
            near_quote = await self.api.get_quote(near_symbol)
            far_quote = await self.api.get_quote(far_symbol)
            
            if direction == "short_spread":
                # 平空近月，多远月
                await self.api.insert_order(
                    symbol=near_symbol,
                    direction="buy",
                    offset="close",
                    volume=volume,
                    limit_price=near_quote["last_price"]
                )
                await self.api.insert_order(
                    symbol=far_symbol,
                    direction="sell",
                    offset="close",
                    volume=volume,
                    limit_price=far_quote["last_price"]
                )
            else:
                # 平多近月，空远月
                await self.api.insert_order(
                    symbol=near_symbol,
                    direction="sell",
                    offset="close",
                    volume=volume,
                    limit_price=near_quote["last_price"]
                )
                await self.api.insert_order(
                    symbol=far_symbol,
                    direction="buy",
                    offset="close",
                    volume=volume,
                    limit_price=far_quote["last_price"]
                )
            
            del self.positions[pair_name]
            if pair_name in self.entry_time:
                del self.entry_time[pair_name]
            print(f"{pair_name}: 平仓成功")
            
        except Exception as e:
            print(f"{pair_name}: 平仓失败 - {e}")
    
    async def run(self):
        """主循环"""
        await self.initialize()
        
        while True:
            try:
                await self.check_and_trade()
                await asyncio.sleep(14400)  # 每4小时检查
            except Exception as e:
                print(f"运行错误: {e}")
                await asyncio.sleep(60)


async def main():
    """主函数"""
    # 回测模式
    api = TqApi(backtest=Backtest(start_date="20240101", end_date="20251231"))
    
    # 实盘模式（取消注释并填入账号）
    # api = TqApi(TqAuth("username", "password"))
    
    strategy = CalendarSpreadArbitrage(api)
    await strategy.run()


if __name__ == "__main__":
    asyncio.run(main())
