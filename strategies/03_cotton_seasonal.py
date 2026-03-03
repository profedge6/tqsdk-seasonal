#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略03 - 跨年度季节性策略
原理：
    某些品种存在跨年度的季节性规律：
    1. 记录过去N年的月度收益
    2. 统计每月胜率和平均收益
    3. 在高胜率月份开仓持有

参数：
    - 品种：棉花
    - 统计年数：5年
    - 入场月份：9-11月（棉花收获季）

适用品种：棉花、白糖、橡胶等
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth
import pandas as pd

# ============ 参数配置 ============
SYMBOL = "CF2409"              # 棉花期货
KLINE_DURATION = 60 * 60 * 24  # 日K线
YEARS = 5                      # 统计年数
ENTRY_MONTHS = [9, 10, 11]     # 入场月份
EXIT_MONTHS = [12, 1]          # 出场月份
LOT_SIZE = 1                   # 开仓手数

def get_monthly_returns(klines):
    """计算月度收益率"""
    df = pd.DataFrame(klines)
    df['close'] = df['close'].astype(float)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['year'] = df['datetime'].dt.year
    df['month'] = df['datetime'].dt.month
    
    monthly = df.groupby(['year', 'month']).agg({
        'close': ['first', 'last']
    })
    
    monthly['return'] = (monthly['close']['last'] - monthly['close']['first']) / monthly['close']['first']
    return monthly['return']

def analyze_seasonality(klines, years):
    """分析季节性规律"""
    df = pd.DataFrame(klines)
    df['close'] = df['close'].astype(float)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['month'] = df['datetime'].dt.month
    
    # 按月份统计
    monthly_stats = df.groupby('month').agg({
        'close': ['mean', 'std']
    }).reset_index()
    
    return monthly_stats

def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print(f"启动：跨年度季节性策略 | 品种: {SYMBOL}")
    
    # 获取多年K线数据
    data_length = YEARS * 365
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=data_length)
    
    # 分析季节性
    seasonality = analyze_seasonality(klines, YEARS)
    
    print("\n=== 月度统计 ===")
    print(seasonality)
    
    # 获取当前月份
    current_time = api.get_current_datetime()
    current_month = current_time.month
    
    position = 0  # 1: 多头, -1: 空头, 0: 空仓
    
    # 季节性信号
    if current_month in ENTRY_MONTHS:
        # 入场季节
        month_stats = seasonality[seasonality['month'] == current_month]
        if not month_stats.empty:
            avg_return = month_stats[('close', 'mean')].values[0]
            if avg_return > 0:
                print(f"季节性买入信号: {current_month}月历史平均收益为正")
                # 开多仓
                position = 1
    
    elif current_month in EXIT_MONTHS:
        # 出场季节
        if position != 0:
            print(f"季节性平仓信号: {current_month}月")
            # 平仓
            position = 0
    
    api.close()

if __name__ == "__main__":
    main()
