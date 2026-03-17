#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
农产品多因子截面策略 - 策略27
Agricultural Multi-Factor Strategy

策略逻辑：
- 截面多因子模型应用于农产品期货（豆粕、玉米、棉花、白糖、苹果）
- 因子：动量、波动率、期限结构、季节性
- 每月调仓，做多强势品种，做空弱势品种
"""

import asyncio
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from tqsdk import TqApi, TqAuth, Backtest, TqSim
from tqsdk.ta import MA, RSI, BOLL


class AgriMultiFactorStrategy:
    """农产品多因子截面策略"""
    
    # 交易标的
    SYMBOLS = [
        "CZCE.m",       # 豆粕主力
        "CZCE.c",       # 玉米主力
        "CZCE.cf",      # 棉花主力
        "CZCE.sr",      # 白糖主力
        "CZCE.ap",      # 苹果主力
    ]
    
    # 因子权重
    FACTOR_WEIGHTS = {
        "momentum": 0.25,         # 动量因子
        "volatility": 0.15,       # 波动率因子
        "term_structure": 0.20,   # 期限结构因子
        "seasonality": 0.25,      # 季节性因子
        "liquidity": 0.15,        # 流动性因子
    }
    
    def __init__(self, api: TqApi):
        self.api = api
        self.positions = {}  # symbol -> position
        self.factor_scores = {}  # symbol -> score
        self.last_rebalance = None
        
    async def initialize(self):
        """初始化策略"""
        print("初始化农产品多因子策略...")
        for symbol in self.SYMBOLS:
            try:
                kline = await self.api.get_kline_serial(symbol, "1d", 60)
                print(f"  已加载 {symbol} 60日K线")
            except Exception as e:
                print(f"  加载 {symbol} 失败: {e}")
    
    async def calculate_factors(self, symbol: str) -> Dict[str, float]:
        """计算单个品种的各因子得分"""
        try:
            kline = await self.api.get_kline_serial(symbol, "1d", 30)
            closes = kline['close'].tolist()
            volumes = kline['volume'].tolist()
            
            if len(closes) < 20:
                return None
            
            # 1. 动量因子 (20日)
            momentum = (closes[-1] - closes[-20]) / closes[-20] * 100 if len(closes) >= 20 else 0
            
            # 2. 波动率因子 (20日年化) - 低波动率是好事
            returns = [closes[i+1]/closes[i] - 1 for i in range(len(closes)-1) if i < 19]
            if len(returns) > 1:
                volatility = pd.Series(returns).std() * (252 ** 0.5)
            else:
                volatility = 0
            # 转换为低波动率高得分
            volatility_score = -volatility * 10
            
            # 3. 期限结构因子 (近月-远月)
            try:
                # 使用5日均价和20日均价差异
                ma5 = sum(closes[-5:]) / 5
                ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
                term_structure = (ma5 - ma20) / ma20 * 100
            except:
                term_structure = 0
            
            # 4. 季节性因子 (基于月份)
            current_month = datetime.now().month
            # 农产品季节性规律
            season_map = {
                1: 0.2,   # 冬季
                2: 0.2,   # 冬季
                3: 0.5,   # 春耕
                4: 0.8,   # 春耕
                5: 0.6,   # 生长期
                6: 0.6,   # 生长期
                7: 0.4,   # 夏季
                8: 0.3,   # 收获前
                9: -0.3,  # 收获期
                10: -0.5, # 收获期
                11: 0.0,  # 冬季前
                12: 0.1,  # 冬季
            }
            seasonality = season_map.get(current_month, 0)
            
            # 5. 流动性因子 (成交量变化)
            if len(volumes) >= 20 and sum(volumes[:10]) > 0:
                vol_change = (sum(volumes[-10:]) / sum(volumes[:10]) - 1)
            else:
                vol_change = 0
            liquidity = vol_change * 10
            
            return {
                "momentum": momentum,
                "volatility": volatility_score,
                "term_structure": term_structure,
                "seasonality": seasonality,
                "liquidity": liquidity
            }
        except Exception as e:
            print(f"计算因子失败 {symbol}: {e}")
            return None
    
    def normalize_factor(self, values: List[float]) -> List[float]:
        """Z-score标准化因子"""
        if not values or len(values) < 2:
            return values
        mean = sum(values) / len(values)
        std = (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5
        if std == 0:
            return [0] * len(values)
        return [(x - mean) / std for x in values]
    
    async def calculate_scores(self) -> Dict[str, float]:
        """计算所有品种的综合得分"""
        factors_data = {}
        
        for symbol in self.SYMBOLS:
            factors = await self.calculate_factors(symbol)
            if factors:
                factors_data[symbol] = factors
        
        if not factors_data:
            return {}
        
        # 标准化各因子
        normalized = {}
        for factor_name in self.FACTOR_WEIGHTS.keys():
            values = [data[factor_name] for data in factors_data.values()]
            norm_values = self.normalize_factor(values)
            for i, symbol in enumerate(factors_data.keys()):
                if symbol not in normalized:
                    normalized[symbol] = {}
                normalized[symbol][factor_name] = norm_values[i]
        
        # 计算加权得分
        scores = {}
        for symbol, norm_factors in normalized.items():
            score = sum(
                norm_factors[factor] * weight 
                for factor, weight in self.FACTOR_WEIGHTS.items()
            )
            scores[symbol] = score
        
        return scores
    
    async def rebalance(self):
        """调仓：做多最强，做空最弱"""
        current_time = datetime.now()
        
        # 每月调仓
        if self.last_rebalance:
            days_since = (current_time - self.last_rebalance).days
            if days_since < 5:  # 至少5天调仓一次
                return
        
        print("\n=== 农产品多因子策略执行调仓 ===")
        scores = await self.calculate_scores()
        
        if not scores:
            return
        
        # 排序
        sorted_symbols = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        print(f"品种得分排序: {sorted_symbols}")
        
        # 平掉现有仓位
        await self.close_all_positions()
        
        # 做多得分最高的品种
        long_symbol = sorted_symbols[0][0]
        # 做空得分最低的品种
        short_symbol = sorted_symbols[-1][0]
        
        # 开多仓
        await self.open_position(long_symbol, 1, "long")
        print(f"做多 {long_symbol}")
        
        # 开空仓
        await self.open_position(short_symbol, 1, "short")
        print(f"做空 {short_symbol}")
        
        self.last_rebalance = current_time
    
    async def open_position(self, symbol: str, volume: int, direction: "long" | "short"):
        """开仓"""
        try:
            quote = await self.api.get_quote(symbol)
            await self.api.insert_order(
                symbol=symbol,
                direction="buy" if direction == "long" else "sell",
                offset="open",
                volume=volume,
                limit_price=quote["last_price"]
            )
            self.positions[symbol] = {
                "direction": direction,
                "volume": volume
            }
        except Exception as e:
            print(f"开仓失败 {symbol}: {e}")
    
    async def close_position(self, symbol: str):
        """平仓"""
        if symbol not in self.positions:
            return
        try:
            quote = await self.api.get_quote(symbol)
            direction = self.positions[symbol]["direction"]
            volume = self.positions[symbol]["volume"]
            await self.api.insert_order(
                symbol=symbol,
                direction="sell" if direction == "long" else "buy",
                offset="close",
                volume=volume,
                limit_price=quote["last_price"]
            )
            del self.positions[symbol]
        except Exception as e:
            print(f"平仓失败 {symbol}: {e}")
    
    async def close_all_positions(self):
        """平所有仓"""
        for symbol in list(self.positions.keys()):
            await self.close_position(symbol)
    
    async def run(self):
        """主循环"""
        await self.initialize()
        
        while True:
            try:
                await self.rebalance()
                await asyncio.sleep(3600)  # 每小时检查
            except Exception as e:
                print(f"运行错误: {e}")
                await asyncio.sleep(60)


async def main():
    """主函数"""
    # 回测模式
    api = TqApi(backtest=Backtest(start_date="20240101", end_date="20251231"))
    
    # 实盘模式（取消注释并填入账号）
    # api = TqApi(TqAuth("username", "password"))
    
    strategy = AgriMultiFactorStrategy(api)
    await strategy.run()


if __name__ == "__main__":
    asyncio.run(main())
