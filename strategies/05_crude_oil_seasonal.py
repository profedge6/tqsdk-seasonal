#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略05 - 季节性策略：原油季节性交易策略
原理：
    原油价格在特定月份存在季节性规律。
    统计历史数据，找出高概率的月份进行交易。

参数：
    - 合约：SC2505
    - 交易月份：3月、9月
    - 入场时机：月初
    - 止损：3%

适用行情：季节性规律明显时
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth
import pandas as pd
import numpy as np
from datetime import datetime

# ============ 参数配置 ============
SYMBOL = "SC2505"               # 原油
KLINE_DURATION = 60 * 60 * 24   # 日K线
TRADE_MONTHS = [3, 9]          # 交易月份
STOP_LOSS = 0.03                # 3%止损
TAKE_PROFIT = 0.06              # 6%止盈

# ============ 主策略 ============
def get_seasonal_signal(month):
    """根据月份返回季节性信号"""
    
    # 3月和9月通常是原油的转折点
    seasonal_data = {
        3: 1,   # 做多
        9: -1,  # 做空
    }
    
    return seasonal_data.get(month, 0)


def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：原油季节性交易策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=100)
    quote = api.get_quote(SYMBOL)
    
    position = 0
    entry_price = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            current_price = klines['close'].iloc[-1]
            current_month = datetime.now().month
            
            signal = get_seasonal_signal(current_month)
            
            print(f"当前价格: {current_price}, 月份: {current_month}, 信号: {signal}")
            
            if position == 0:
                if signal != 0:
                    position = signal
                    entry_price = current_price
                    print(f"[开仓] {'做多' if signal == 1 else '做空'}, 价格: {current_price}")
                    
            elif position == 1:
                pnl = (current_price - entry_price) / entry_price
                
                if pnl < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}")
                    position = 0
                elif pnl > TAKE_PROFIT:
                    print(f"[止盈] 价格: {current_price}")
                    position = 0
                    
            elif position == -1:
                pnl = (entry_price - current_price) / entry_price
                
                if pnl < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}")
                    position = 0
                elif pnl > TAKE_PROFIT:
                    print(f"[止盈] 价格: {current_price}")
                    position = 0
    
    api.close()

if __name__ == "__main__":
    main()
