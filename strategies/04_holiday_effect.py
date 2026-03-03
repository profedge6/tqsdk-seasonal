#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略04 - 节假日效应策略
原理：
    中国期货市场受节假日影响明显：
    1. 节假日前后波动性增大
    2. 某些品种有特定节假日期规律
    3. 捕捉节假日前后的突破行情

参数：
    - 目标节假日：春节、国庆
    - 入场时机：节前3天
    - 出场时机：节后2天

适用品种：所有期货
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth
import datetime

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2405"       # 螺纹钢
KLINE_DURATION = 60 * 60    # 1小时K线
BEFORE_DAYS = 3              # 节前入场天数
AFTER_DAYS = 2               # 节后出场天数
LOT_SIZE = 1                 # 开仓手数

# 中国主要节假日
HOLIDAYS = [
    ("春节", [1, 2]),        # 春节前后
    ("国庆", [10, 1]),       # 国庆前后
    ("五一", [5, 1]),        # 劳动节
    ("端午", [6, 3]),        # 端午节
    ("中秋", [9, 15]),       # 中秋节
]

def is_holiday_near(current_date, holiday_info):
    """判断是否接近节假日"""
    month, day = holiday_info[1]
    holiday_date = datetime.date(current_date.year, month, day)
    
    days_diff = abs((current_date - holiday_date).days)
    return days_diff <= BEFORE_DAYS + AFTER_DAYS

def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print(f"启动：节假日效应策略 | 品种: {SYMBOL}")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=100)
    
    position = 0  # 1: 多头, -1: 空头, 0: 空仓
    holiday_position = None
    
    while True:
        api.wait_update(klines)
        
        current_time = api.get_current_datetime()
        current_date = current_time.date()
        
        # 检查是否接近节假日
        near_holiday = None
        for name, date_info in HOLIDAYS:
            if is_holiday_near(current_date, (name, date_info)):
                near_holiday = name
                break
        
        if near_holiday:
            if position == 0:
                print(f"接近{near_holiday}，准备入场")
                # 简单策略：高开做多，低开做空
                # 实际需要更复杂逻辑
                position = 1  # 示例做多
        else:
            if position != 0:
                print(f"节假日效应结束，平仓")
                position = 0
    
    api.close()

if __name__ == "__main__":
    main()
