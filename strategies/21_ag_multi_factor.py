#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略21 - 多因子策略：农产品多因子截面策略
原理：
    结合动量因子、波动率因子和期限结构因子的多因子模型。
    在农产品期货中，动量效应和期限结构溢价是常见有效的因子。

参数：
    - 合约池：豆粕、玉米、棉花、白糖（农产品板块）
    - 周期：日K
    - 动量周期：20日
    - 波动率周期：20日
    - 做多因子：动量>0 + 波动率低位 + 期限结构contango
    - 做空因子：动量<0 + 波动率高位 + 期限结构backwardation
    - 止损：2.5%

适用行情：因子信号共振
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth
from tqsdk.ta import MA, ATR
import numpy as np
import datetime

# ============ 参数配置 ============
# 农产品合约池
SYMBOLS = {
    "CZCE.M": "CZCE.M2505",     # 豆粕
    "CZCE.C": "CZCE.C2505",     # 玉米
    "CZCE.CF": "CZCE.CF2505",   # 棉花
    "CZCE.SR": "CZCE.SR2505",   # 白糖
}

KLINE_DURATION = 24 * 60 * 60   # 日K
MOMENTUM_PERIOD = 20            # 动量周期
VOLATILITY_PERIOD = 20          # 波动率周期
STOP_LOSS = 0.025               # 2.5%止损
MAX_POSITION = 2                # 最多持仓2个品种

# ============ 因子计算 ============
def calculate_momentum_factor(klines):
    """动量因子：过去N日收益率"""
    if len(klines) < MOMENTUM_PERIOD + 1:
        return 0
    close = klines['close'].values
    momentum = (close[-1] - close[-MOMENTUM_PERIOD]) / close[-MOMENTUM_PERIOD]
    return momentum

def calculate_volatility_factor(klines):
    """波动率因子：过去N日收益率标准差（年化）"""
    if len(klines) < VOLATILITY_PERIOD + 1:
        return 0.15  # 默认中等波动率
    returns = np.diff(klines['close'].values[-VOLATILITY_PERIOD:]) / klines['close'].values[-VOLATILITY_PERIOD:-1]
    volatility = np.std(returns) * np.sqrt(252)
    return volatility

def calculate_term_structure(klines):
    """期限结构因子：近月合约 vs 远月合约（简化：使用收盘价vs20日均价）"""
    if len(klines) < 20:
        return 0
    current_price = klines['close'].iloc[-1]
    ma20 = klines['close'].rolling(20).mean().iloc[-1]
    # contango (升水) > 0, backwardation (贴水) < 0
    term_structure = (current_price - ma20) / ma20
    return term_structure

def calculate_factors(api, symbol):
    """计算单个品种的因子值"""
    try:
        klines = api.get_kline_serial(symbol, KLINE_DURATION, data_length=VOLATILITY_PERIOD + 30)
        if len(klines) < VOLATILITY_PERIOD + 10:
            return None
        
        momentum = calculate_momentum_factor(klines)
        volatility = calculate_volatility_factor(klines)
        term_structure = calculate_term_structure(klines)
        
        return {
            'momentum': momentum,
            'volatility': volatility,
            'term_structure': term_structure,
            'close': klines['close'].iloc[-1]
        }
    except Exception as e:
        print(f"获取{symbol}数据失败: {e}")
        return None

def generate_multi_factor_signal(factors):
    """
    多因子打分模型
    动量因子：>0 得1分，<0 扣1分
    波动率因子：低于中位数(0.15)得1分，高于扣1分
    期限结构：contango得1分，backwardation扣1分
    """
    if factors is None:
        return 0, "数据不足"
    
    score = 0
    
    # 动量因子打分
    if factors['momentum'] > 0.02:  # 2%以上动量
        score += 1.5
        momentum_reason = "强动量"
    elif factors['momentum'] > 0:
        score += 0.5
        momentum_reason = "弱动量"
    elif factors['momentum'] < -0.02:
        score -= 1.5
        momentum_reason = "强负动量"
    else:
        score -= 0.5
        momentum_reason = "弱负动量"
    
    # 波动率因子打分
    if factors['volatility'] < 0.10:  # 低波动
        score += 1
        vol_reason = "低波动"
    elif factors['volatility'] > 0.25:  # 高波动
        score -= 1
        vol_reason = "高波动"
    else:
        vol_reason = "中等波动"
    
    # 期限结构打分
    if factors['term_structure'] > 0.005:
        score += 1
        term_reason = "Contango(升水)"
    elif factors['term_structure'] < -0.005:
        score -= 1
        term_reason = "Backwardation(贴水)"
    else:
        term_reason = "平水"
    
    if score >= 2.5:
        return 1, f"{momentum_reason}+{vol_reason}+{term_reason}, 多因子得分:{score:.1f}"
    elif score <= -2.5:
        return -1, f"{momentum_reason}+{vol_reason}+{term_reason}, 多因子得分:{score:.1f}"
    else:
        return 0, f"因子中性, 得分:{score:.1f}"

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：农产品多因子截面策略")
    print(f"交易品种: {list(SYMBOLS.keys())}")
    
    # 持仓: {symbol: {'position': 1/-1, 'entry_price': float, 'name': str}}
    positions = {}
    
    while True:
        try:
            # 遍历所有品种计算因子
            signals = {}
            for name, symbol in SYMBOLS.items():
                factors = calculate_factors(api, symbol)
                if factors:
                    signal, reason = generate_multi_factor_signal(factors)
                    signals[name] = {
                        'signal': signal,
                        'reason': reason,
                        'factors': factors
                    }
                    print(f"{name}: {reason}")
            
            # 筛选做多信号（得分最高的2个）
            long_signals = [(name, s) for name, s in signals.items() if s['signal'] == 1]
            long_signals.sort(key=lambda x: x[1]['factors']['momentum'], reverse=True)
            
            short_signals = [(name, s) for name, s in signals.items() if s['signal'] == -1]
            short_signals.sort(key=lambda x: x[1]['factors']['momentum'])
            
            # 更新持仓
            current_month = datetime.datetime.now().month
            
            # 处理平仓（季节性过滤）
            # 12-2月冬季不建议做多农产品
            if current_month in [12, 1, 2]:
                if positions:
                    print("冬季期间，平仓所有多头")
                    for name, pos in list(positions.items()):
                        if pos['position'] == 1:
                            print(f"[平仓] {name} 多头")
                            del positions[name]
            
            # 止盈止损检查
            for name, pos in list(positions.items()):
                symbol = SYMBOLS[name]
                klines = api.get_kline_serial(symbol, KLINE_DURATION, data_length=5)
                current_price = klines['close'].iloc[-1]
                
                if pos['position'] == 1:  # 多头
                    if current_price < pos['entry_price'] * (1 - STOP_LOSS):
                        print(f"[止损] {name} 多头, 价格: {current_price}")
                        del positions[name]
                    elif current_price > pos['entry_price'] * (1 + 0.05):  # 5%止盈
                        print(f"[止盈] {name} 多头, 价格: {current_price}")
                        del positions[name]
                elif pos['position'] == -1:  # 空头
                    if current_price > pos['entry_price'] * (1 + STOP_LOSS):
                        print(f"[止损] {name} 空头, 价格: {current_price}")
                        del positions[name]
                    elif current_price < pos['entry_price'] * (1 - 0.05):
                        print(f"[止盈] {name} 空头, 价格: {current_price}")
                        del positions[name]
            
            # 开仓决策
            if len(positions) < MAX_POSITION:
                # 做多
                for name, signal in long_signals[:MAX_POSITION - len(positions)]:
                    if name not in positions:
                        symbol = SYMBOLS[name]
                        klines = api.get_kline_serial(symbol, KLINE_DURATION, data_length=5)
                        current_price = klines['close'].iloc[-1]
                        positions[name] = {
                            'position': 1,
                            'entry_price': current_price,
                            'name': name
                        }
                        print(f"[开多] {name}, 价格: {current_price}, 原因: {signal['reason']}")
                
                # 做空
                for name, signal in short_signals[:MAX_POSITION - len(positions)]:
                    if name not in positions:
                        symbol = SYMBOLS[name]
                        klines = api.get_kline_serial(symbol, KLINE_DURATION, data_length=5)
                        current_price = klines['close'].iloc[-1]
                        positions[name] = {
                            'position': -1,
                            'entry_price': current_price,
                            'name': name
                        }
                        print(f"[开空] {name}, 价格: {current_price}, 原因: {signal['reason']}")
            
            api.wait_update(60)  # 每分钟检查一次
            
        except KeyboardInterrupt:
            print("策略停止")
            break
        except Exception as e:
            print(f"错误: {e}")
            api.wait_update(10)

    api.close()

if __name__ == "__main__":
    main()
