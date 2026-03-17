#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
能源化工价差套利策略 - 策略28
Energy & Chemical Spread Arbitrage Strategy

策略逻辑：
- 跨品种价差套利策略（原油-燃料油、螺纹钢-热卷、焦煤-焦炭）
- 基于产业链上下游关系和替代性
- 当价差偏离历史均值时进行套利
- 价差回归时平仓获利
"""

import asyncio
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from tqsdk import TqApi, TqAuth, Backtest, TqSim
from tqsdk.ta import MA, STD


class EnergySpreadArbitrageStrategy:
    """能源化工价差套利策略"""
    
    # 价差交易对 (产业链相关品种)
    SPREAD_PAIRS = [
        {"name": "原油燃料油", "long": "SC", "short": "FU", "ratio": 1},
        {"name": "螺纹热卷", "long": "RB", "short": "HC", "ratio": 1},
        {"name": "焦煤焦炭", "long": "JM", "short": "J", "ratio": 1},
        {"name": "大豆豆粕", "long": "A", "short": "M", "ratio": 1},
    ]
    
    # 策略参数
    SPREAD_WINDOW = 30        # 计算价差均值的历史窗口
    ENTRY_THRESHOLD = 1.5     # 入场阈值（标准差倍数）
    EXIT_THRESHOLD = 0.5      # 出场阈值（标准差倍数）
    POSITION_SIZE = 1         # 每对交易的手数
    
    def __init__(self, api: TqApi):
        self.api = api
        self.positions = {}  # pair_name -> {"long": symbol, "short": symbol, "spread": float}
        self.spread_history = {}  # pair_name -> list of historical spreads
        self.last_rebalance = None
        
    async def initialize(self):
        """初始化策略"""
        print("初始化能源化工价差套利策略...")
        for pair in self.SPREAD_PAIRS:
            pair_name = pair["name"]
            try:
                # 获取两个品种的历史数据
                long_kline = await self.api.get_kline_serial(pair["long"], "1d", self.SPREAD_WINDOW + 10)
                short_kline = await self.api.get_kline_serial(pair["short"], "1d", self.SPREAD_WINDOW + 10)
                print(f"  已加载 {pair_name}: {pair['long']} & {pair['short']}")
            except Exception as e:
                print(f"  加载 {pair_name} 失败: {e}")
    
    async def calculate_spread(self, long_symbol: str, short_symbol: str, ratio: int = 1) -> Optional[float]:
        """计算价差"""
        try:
            long_quote = await self.api.get_quote(long_symbol)
            short_quote = await self.api.get_quote(short_symbol)
            
            long_price = long_quote.get("last_price", 0)
            short_price = short_quote.get("last_price", 0)
            
            if long_price == 0 or short_price == 0:
                return None
            
            # 价差 = 多头价格 - 空头价格（可根据品种特性调整）
            spread = long_price - short_price * ratio
            return spread
        except Exception as e:
            print(f"计算价差失败: {e}")
            return None
    
    async def calculate_spread_stats(self, pair_name: str) -> Dict[str, float]:
        """计算价差的统计特征"""
        try:
            # 从历史K线计算历史价差
            pair = next(p for p in self.SPREAD_PAIRS if p["name"] == pair_name)
            long_symbol = pair["long"]
            short_symbol = pair["short"]
            ratio = pair.get("ratio", 1)
            
            # 获取历史K线
            long_kline = await self.api.get_kline_serial(long_symbol, "1d", self.SPREAD_WINDOW + 5)
            short_kline = await self.api.get_kline_serial(short_symbol, "1d", self.SPREAD_WINDOW + 5)
            
            long_closes = long_kline['close'].tolist()
            short_closes = short_kline['close'].tolist()
            
            if len(long_closes) < self.SPREAD_WINDOW or len(short_closes) < self.SPREAD_WINDOW:
                return None
            
            # 计算历史价差序列
            spreads = []
            for i in range(-self.SPREAD_WINDOW, 0):
                if i >= -len(long_closes) and (i + len(long_closes) - len(short_closes)) >= -len(short_closes):
                    long_p = long_closes[i]
                    short_p = short_closes[i]
                    if long_p > 0 and short_p > 0:
                        spread = long_p - short_p * ratio
                        spreads.append(spread)
            
            if len(spreads) < 10:
                return None
            
            # 计算均值和标准差
            mean_spread = sum(spreads) / len(spreads)
            variance = sum((s - mean_spread) ** 2 for s in spreads) / len(spreads)
            std_spread = variance ** 0.5
            
            # 当前价差
            current_spread = await self.calculate_spread(long_symbol, short_symbol, ratio)
            
            if current_spread is None:
                return None
            
            return {
                "mean": mean_spread,
                "std": std_spread,
                "current": current_spread,
                "z_score": (current_spread - mean_spread) / std_spread if std_spread > 0 else 0
            }
        except Exception as e:
            print(f"计算价差统计失败 {pair_name}: {e}")
            return None
    
    async def check_spread_pair(self, pair: Dict) -> Tuple[str, str, str]:
        """检查单个价差对是否需要交易"""
        pair_name = pair["name"]
        long_symbol = pair["long"]
        short_symbol = pair["short"]
        
        stats = await self.calculate_spread_stats(pair_name)
        
        if stats is None:
            return "none", "", ""
        
        z_score = stats["z_score"]
        current = stats["current"]
        mean = stats["mean"]
        
        print(f"\n{pair_name}:")
        print(f"  当前价差: {current:.2f}, 历史均值: {mean:.2f}")
        print(f"  Z-Score: {z_score:.2f}")
        
        # 检查是否持有该交易对
        has_position = pair_name in self.positions
        
        if not has_position:
            # 无仓位，检查是否入场
            if z_score > self.ENTRY_THRESHOLD:
                # 价差高于均值，做空价差（空long，多short）
                return "short_spread", long_symbol, short_symbol
            elif z_score < -self.ENTRY_THRESHOLD:
                # 价差低于均值，做多价差（多long，空short）
                return "long_spread", long_symbol, short_symbol
        else:
            # 有仓位，检查是否出场
            if abs(z_score) < self.EXIT_THRESHOLD:
                # 价差回归，平仓
                return "close", long_symbol, short_symbol
            elif z_score > self.ENTRY_THRESHOLD * 2 or z_score < -self.ENTRY_THRESHOLD * 2:
                # 价差继续扩大，止损
                return "stop_loss", long_symbol, short_symbol
        
        return "hold", "", ""
    
    async def rebalance(self):
        """调仓检查"""
        current_time = datetime.now()
        
        # 每天检查一次
        if self.last_rebalance:
            hours_since = (current_time - self.last_rebalance).hours
            if hours_since < 6:  # 至少6小时检查一次
                return
        
        print("\n=== 能源化工价差套利策略执行 ===")
        
        for pair in self.SPREAD_PAIRS:
            action, long_symbol, short_symbol = await self.check_spread_pair(pair)
            pair_name = pair["name"]
            
            if action == "short_spread":
                # 做空价差：空long，多short
                print(f"做空价差 {pair_name}: 空{long_symbol}, 多{short_symbol}")
                await self.open_spread_pair(pair_name, long_symbol, short_symbol, "short")
                
            elif action == "long_spread":
                # 做多价差：多long，空short
                print(f"做多价差 {pair_name}: 多{long_symbol}, 空{short_symbol}")
                await self.open_spread_pair(pair_name, long_symbol, short_symbol, "long")
                
            elif action == "close" or action == "stop_loss":
                # 平仓
                print(f"平仓 {pair_name}")
                await self.close_spread_pair(pair_name)
        
        self.last_rebalance = current_time
    
    async def open_spread_pair(self, pair_name: str, long_symbol: str, short_symbol: str, direction: str):
        """开价差仓"""
        try:
            # 平掉现有仓位
            if pair_name in self.positions:
                await self.close_spread_pair(pair_name)
            
            volume = self.POSITION_SIZE
            
            # 根据方向开仓
            if direction == "short":
                # 做空价差：空long，多short
                await self.open_single_position(long_symbol, volume, "sell")
                await self.open_single_position(short_symbol, volume, "buy")
            else:
                # 做多价差：多long，空short
                await self.open_single_position(long_symbol, volume, "buy")
                await self.open_single_position(short_symbol, volume, "sell")
            
            self.positions[pair_name] = {
                "long": long_symbol,
                "short": short_symbol,
                "direction": direction
            }
        except Exception as e:
            print(f"开价差仓失败 {pair_name}: {e}")
    
    async def close_spread_pair(self, pair_name: str):
        """平价差仓"""
        if pair_name not in self.positions:
            return
        
        try:
            pos = self.positions[pair_name]
            long_symbol = pos["long"]
            short_symbol = pos["short"]
            direction = pos["direction"]
            volume = self.POSITION_SIZE
            
            # 反向平仓
            if direction == "short":
                # 做空价差平仓：多long，空short
                await self.open_single_position(long_symbol, volume, "buy")
                await self.open_single_position(short_symbol, volume, "sell")
            else:
                # 做多价差平仓：空long，多short
                await self.open_single_position(long_symbol, volume, "sell")
                await self.open_single_position(short_symbol, volume, "buy")
            
            del self.positions[pair_name]
        except Exception as e:
            print(f"平价差仓失败 {pair_name}: {e}")
    
    async def open_single_position(self, symbol: str, volume: int, direction: str):
        """单品种开仓"""
        try:
            quote = await self.api.get_quote(symbol)
            await self.api.insert_order(
                symbol=symbol,
                direction=direction,  # "buy" or "sell"
                offset="open",
                volume=volume,
                limit_price=quote["last_price"]
            )
        except Exception as e:
            print(f"开仓失败 {symbol}: {e}")
    
    async def run(self):
        """主循环"""
        await self.initialize()
        
        while True:
            try:
                await self.rebalance()
                await asyncio.sleep(3600 * 6)  # 每6小时检查
            except Exception as e:
                print(f"运行错误: {e}")
                await asyncio.sleep(60)


async def main():
    """主函数"""
    # 回测模式
    api = TqApi(backtest=Backtest(start_date="20240101", end_date="20251231"))
    
    # 实盘模式（取消注释并填入账号）
    # api = TqApi(TqAuth("username", "password"))
    
    strategy = EnergySpreadArbitrageStrategy(api)
    await strategy.run()


if __name__ == "__main__":
    asyncio.run(main())
