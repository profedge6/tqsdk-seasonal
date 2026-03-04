#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略07 - 季节性策略：PTA季节性趋势策略
原理：
    PTA（精对苯二甲酸）具有明显的季节性特征。
    根据历史统计，春季和秋季需求旺季往往上涨。

参数：
    - 合约：TA2505
    - 周期：日K
    - 均线：20日
    - 止损：3%

适用行情：季节性旺季
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth
from tqsdk.ta import MA
import numpy as np

# ============ 参数配置 ============
SYMBOL = "CZCE.TA2505"          # PTA合约
KLINE_DURATION = 24 * 60 * 60   # 日K
MA_PERIOD = 20                   # 均线周期
STOP_LOSS = 0.03                # 3%止损

# ============ 季节性分析 ============
def get_seasonal_signal(month):
    """
    基于月份的季节性信号
    3-5月: 春季旺季，做多
    9-11月: 秋季旺季，做多
    6-8月: 淡季，做空
    12-2月: 冬季，观察
    """
    if month in [3, 4, 5]:
        return 1, "春季旺季"
    elif month in [9, 10, 11]:
        return 1, "秋季旺季"
    elif month in [6, 7, 8]:
        return -1, "夏季淡季"
    else:
        return 0, "冬季观察"

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：PTA季节性趋势策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=MA_PERIOD + 10)
    
    position = 0
    entry_price = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < MA_PERIOD:
                continue
                
            ma = MA(klines, MA_PERIOD).iloc[-1]
            current_price = klines['close'].iloc[-1]
            
            # 获取当前月份
            import datetime
            month = datetime.datetime.now().month
            
            signal, reason = get_seasonal_signal(month)
            
            print(f"价格: {current_price}, MA20: {ma:.2f}, 月份: {month}月, 信号: {reason}")
            
            if position == 0:
                # 季节性做多
                if signal == 1 and current_price > ma:
                    position = 1
                    entry_price = current_price
                    print(f"[买入] 季节性做多, 价格: {current_price}")
                # 季节性做空
                elif signal == -1 and current_price < ma:
                    position = -1
                    entry_price = current_price
                    print(f"[卖出] 季节性做空, 价格: {current_price}")
                    
            elif position == 1:
                if current_price < entry_price * (1 - STOP_LOSS):
                    print(f"[止损] 价格: {current_price}")
                    position = 0
                elif signal == 0:
                    print(f"[平仓] 季节性信号消失")
                    position = 0
                    
            elif position == -1:
                if current_price > entry_price * (1 + STOP_LOSS):
                    print(f"[止损] 价格: {current_price}")
                    position = 0
                elif signal == 0:
                    print(f"[平仓] 季节性信号消失")
                    position = 0
    
    api.close()

if __name__ == "__main__":
    main()
