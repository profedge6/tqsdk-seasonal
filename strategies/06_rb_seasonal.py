#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略06 - 季节性策略：螺纹钢季节性交易策略
原理：
    螺纹钢需求具有明显的季节性特征。
    春季和秋季是需求旺季，价格倾向于上涨。
    冬季是需求淡季，价格倾向于下跌。

参数：
    - 合约：SHFE.rb2505
    - 旺季月份：3-5月, 9-11月
    - 淡季月份：12-2月, 6-8月
    - 止损：3%

适用行情：季节性规律明显时
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth
import pandas as pd
import numpy as np
from datetime import datetime

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 60 * 60 * 24   # 日K线
PEAK_MONTHS = [3, 4, 5, 9, 10, 11]  # 旺季
OFF_MONTHS = [12, 1, 2]        # 淡季
STOP_LOSS = 0.03                # 3%止损
TAKE_PROFIT = 0.05              # 5%止盈

# ============ 主策略 ============
def get_seasonal_signal(month):
    """根据月份返回季节性信号"""
    
    if month in PEAK_MONTHS:
        return 1   # 做多
    elif month in OFF_MONTHS:
        return -1  # 做空
    else:
        return 0   # 观望


def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：螺纹钢季节性交易策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=50)
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
                    season = "旺季" if signal == 1 else "淡季"
                    print(f"[开仓] {season}做{'多' if signal == 1 else '空'}, 价格: {current_price}")
                    
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
