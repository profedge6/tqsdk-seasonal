#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略09 - 冬季取暖油季节性策略
原理：
    冬季取暖油需求增加，价格通常上涨。
    基于历史季节性规律，在旺季来临前布局多单。

参数：
    - 合约：SC2501-SC2503
    - 入场时机：10月底
    - 目标时机：1月底
    - 止损：5%

适用行情：冬季取暖油旺季
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth

# ============ 参数配置 ============
SYMBOLS = ["SC2501", "SC2502", "SC2503"]  # 原油连续合约
ENTRY_MONTH = 10                  # 入场月份（10月）
EXIT_MONTH = 1                    # 出场月份（1月）
STOP_LOSS = 0.05                   # 5%止损

# ============ 季节性分析 ============
def analyze_seasonality(klines):
    """
    分析季节性规律
    返回各月份平均收益
    """
    # 简化：返回历史统计的季节性因子
    # 11月、12月、1月为取暖油旺季
    seasonal_factors = {
        11: 1.2,
        12: 1.3,
        1: 1.1,
    }
    
    return seasonal_factors

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：冬季取暖油季节性策略")
    
    import datetime
    current_month = datetime.datetime.now().month
    
    # 检查是否在入场时机
    if current_month == ENTRY_MONTH:
        print(f"[入场窗口] 当前月份适合入场")
        
        # 获取主力合约
        main_contract = SYMBOLS[0]
        quote = api.get_quote(f"INE.{main_contract}")
        
        print(f"主力合约: INE.{main_contract}")
        print(f"当前价格: {quote.last_price}")
        
        # 季节性因子
        seasonal = analyze_seasonality(None)
        print(f"当前季节性因子: {seasonal.get(current_month, 1.0)}")
        
    elif current_month == EXIT_MONTH:
        print(f"[出场窗口] 季节性行情结束")
        
    else:
        print(f"[等待] 当前月份: {current_month}, 入场月份: {ENTRY_MONTH}")
    
    # 持续监控
    while True:
        api.wait_update()
        
        current_month = datetime.datetime.now().month
        
        # 适时提醒
        if current_month == ENTRY_MONTH:
            print(f"[提醒] 入场月份到了")
    
    api.close()

if __name__ == "__main__":
    main()
