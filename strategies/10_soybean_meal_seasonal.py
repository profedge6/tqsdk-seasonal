#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略10 - 春季豆粕季节性策略
原理：
    春季养殖业补栏带动豆粕需求，同时南美大豆上市影响供应。
    基于历史季节性规律，在需求旺季来临前布局。

参数：
    - 合约：DCE.m2505
    - 入场时机：3月初
    - 目标时机：5月底
    - 止损：4%

适用行情：春季豆粕需求旺季
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth

# ============ 参数配置 ============
SYMBOL = "DCE.m2505"             # 豆粕
ENTRY_MONTH = 3                  # 入场月份（3月）
EXIT_MONTH = 5                   # 出场月份（5月）
STOP_LOSS = 0.04                 # 4%止损

# ============ 季节性分析 ============
def get_seasonal_factor(month):
    """获取季节性因子"""
    # 豆粕季节性规律
    # 3-5月：养殖补栏，需求上升
    seasonal = {
        1: 0.9, 2: 0.9, 3: 1.1, 4: 1.2, 5: 1.1,
        6: 1.0, 7: 1.0, 8: 1.0, 9: 1.0, 10: 1.0, 11: 0.9, 12: 0.9
    }
    return seasonal.get(month, 1.0)

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：春季豆粕季节性策略")
    
    import datetime
    current_month = datetime.datetime.now().month
    
    quote = api.get_quote(SYMBOL)
    klines = api.get_kline_serial(SYMBOL, 24*60*60, data_length=60)
    
    position = 0
    entry_price = 0
    
    # 季节性因子
    seasonal_factor = get_seasonal_factor(current_month)
    print(f"当前月份: {current_month}, 季节性因子: {seasonal_factor}")
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            current_price = klines['close'].iloc[-1]
            
            # 检查是否需要交易
            month = datetime.datetime.now().month
            
            # 入场条件
            if position == 0 and month == ENTRY_MONTH:
                seasonal = get_seasonal_factor(month)
                if seasonal > 1.0:
                    position = 1
                    entry_price = current_price
                    print(f"[买入] 入场季节性多单，价格: {current_price}")
            
            # 持仓管理
            elif position == 1:
                pnl_pct = (current_price - entry_price) / entry_price
                
                # 止损
                if pnl_pct < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}, 亏损{pnl_pct*100:.1f}%")
                    position = 0
                
                # 目标出场
                elif month == EXIT_MONTH:
                    print(f"[平仓] 季节性行情结束，价格: {current_price}, 盈利{pnl_pct*100:.1f}%")
                    position = 0
            
            print(f"当前价格: {current_price}, 持仓: {position}")
    
    api.close()

if __name__ == "__main__":
    main()
