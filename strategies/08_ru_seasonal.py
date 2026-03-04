#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略08 - 季节性策略：橡胶季节性反转策略
原理：
    橡胶（RU）具有明显的季节性特征。
    根据历史统计，在特定月份进行反转交易。

参数：
    - 合约：SHFE.ru2505
    - 周期：日K
    - 均线：60日
    - 止损：4%

适用行情：季节性转折点
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth
from tqsdk.ta import MA
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.ru2505"          # 橡胶合约
KLINE_DURATION = 24 * 60 * 60   # 日K
MA_PERIOD = 60                   # 均线周期
STOP_LOSS = 0.04                # 4%止损

# ============ 季节性分析 ============
def get_seasonal反转(month):
    """
    基于月份的季节性反转信号
    1-2月: 年初低点可能反转
    5-6月: 割胶旺季可能下跌
    11-12月: 年末可能反弹
    """
    if month in [1, 2, 11, 12]:
        return 1, "年末/年初反弹周期"
    elif month in [5, 6]:
        return -1, "割胶旺季下跌"
    else:
        return 0, "观望"

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：橡胶季节性反转策略")
    
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
            
            signal, reason = get_seasonal反转(month)
            
            print(f"价格: {current_price}, MA60: {ma:.2f}, 月份: {month}月, 信号: {reason}")
            
            if position == 0:
                # 季节性反转做多
                if signal == 1 and current_price < ma:
                    position = 1
                    entry_price = current_price
                    print(f"[买入] 季节性反转, 价格: {current_price}")
                # 季节性做空
                elif signal == -1 and current_price > ma:
                    position = -1
                    entry_price = current_price
                    print(f"[卖出] 割胶旺季, 价格: {current_price}")
                    
            elif position == 1:
                if current_price < entry_price * (1 - STOP_LOSS):
                    print(f"[止损] 价格: {current_price}")
                    position = 0
                elif current_price > ma:
                    print(f"[平仓] 突破均线")
                    position = 0
                    
            elif position == -1:
                if current_price > entry_price * (1 + STOP_LOSS):
                    print(f"[止损] 价格: {current_price}")
                    position = 0
                elif current_price < ma:
                    print(f"[平仓] 跌破均线")
                    position = 0
    
    api.close()

if __name__ == "__main__":
    main()
