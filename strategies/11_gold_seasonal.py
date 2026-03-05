#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略11 - 黄金季节性交易策略
原理：
    利用黄金期货的季节性规律进行交易
    黄金在特定月份往往表现较好

参数：
    - 合约：SHFE.au2506
    - 周期：日线
    - 交易月份：1月、8月、9月

适用行情：季节性行情
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from datetime import datetime

# ============ 参数配置 ============
SYMBOL = "SHFE.au2506"           # 黄金期货
KLINE_DURATION = 24 * 60 * 60    # 日线
TRADE_MONTHS = [1, 8, 9]         # 交易月份
VOLUME = 1                       # 每次交易手数
DATA_LENGTH = 50                 # 历史K线数量


def main():
    api = TqApi(account=TqSim(), auth=TqAuth("账号", "密码"))
    print("启动：黄金季节性交易策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, DATA_LENGTH)
    target_pos = TargetPosTask(api, SYMBOL)
    
    position = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines.iloc[-1], "datetime"):
            dt = datetime.now()
            current_month = dt.month
            
            # 检查是否在交易月份
            in_trade_month = current_month in TRADE_MONTHS
            
            if position == 0 and in_trade_month:
                print(f"[开仓] 进入交易月份{current_month}月，做多")
                target_pos.set_target_volume(VOLUME)
                position = 1
            elif position == 1 and not in_trade_month:
                print(f"[平仓] 离开交易月份{current_month}月，平仓")
                target_pos.set_target_volume(0)
                position = 0
    
    api.close()


if __name__ == "__main__":
    main()
