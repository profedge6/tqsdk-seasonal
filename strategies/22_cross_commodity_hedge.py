#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略22 - 跨品种对冲策略：能源与金属产业链对冲
原理：
    基于产业链逻辑的跨品种对冲策略。
    原油(SC)上涨通常带动化工品(PTA/Methanol)成本上升，
    同时也会影响金属(铜/铝)的能源成本和需求预期。
    
    策略逻辑：
    - 原油 vs 化工品：成本推动逻辑
    - 铜 vs 铝：需求联动逻辑
    - 当产业链价差偏离历史均值时，做均值回归交易

参数：
    - 交易对1：SC(原油) vs PTA(化工)
    - 交易对2：CU(铜) vs AL(铝)
    - 周期：日K
    - 布林带周期：20日
    - 布林带标准差：2
    - 止损：2%

适用行情：产业链价差偏离
作者：profedge6 / tqsdk-seasonal
"""

from tqsdk import TqApi, TqAuth
from tqsdk.ta import MA, BOLL
import numpy as np
import datetime

# ============ 参数配置 ============
# 交易对配置
PAIRS = {
    "SC_PTA": {
        "long": "SHFE.SC2505",    # 原油
        "short": "CZCE.TA2505",  # PTA
        "name": "原油-化工"
    },
    "CU_AL": {
        "long": "SHFE.CU2505",    # 铜
        "short": "SHFE.AL2505",  # 铝
        "name": "铜-铝"
    }
}

KLINE_DURATION = 24 * 60 * 60   # 日K
BOLL_PERIOD = 20                # 布林带周期
BOLL_STD = 2                    # 布林带标准差倍数
STOP_LOSS = 0.02                # 2%止损
HISTORY_PERIOD = 60             # 历史数据周期

# ============ 对冲逻辑 ============
def calculate_spread(api, long_symbol, short_symbol):
    """
    计算跨品种价差
    由于不同品种价格量级不同，使用价格比值
    """
    try:
        long_klines = api.get_kline_serial(long_symbol, KLINE_DURATION, data_length=HISTORY_PERIOD + 10)
        short_klines = api.get_kline_serial(short_symbol, KLINE_DURATION, data_length=HISTORY_PERIOD + 10)
        
        if len(long_klines) < HISTORY_PERIOD or len(short_klines) < HISTORY_PERIOD:
            return None, None, None
        
        long_price = long_klines['close'].iloc[-1]
        short_price = short_klines['close'].iloc[-1]
        
        # 使用价格比值作为价差指标（归一化）
        spread = long_price / short_price
        
        # 计算历史统计
        spreads = long_klines['close'].values[-HISTORY_PERIOD:] / short_klines['close'].values[-HISTORY_PERIOD:]
        
        ma = np.mean(spreads)
        std = np.std(spreads)
        
        # 布林带
        upper = ma + BOLL_STD * std
        lower = ma - BOLL_STD * std
        
        # z-score
        z_score = (spread - ma) / std if std > 0 else 0
        
        return spread, (lower, ma, upper), z_score
        
    except Exception as e:
        print(f"计算价差失败: {e}")
        return None, None, None

def generate_pair_signal(spread, boll, z_score):
    """
    基于布林带的均值回归信号
    z_score > 2: 做空价差（做多short，做空long）
    z_score < -2: 做多价差（做多long，做空short）
    z_score 回归到 0 附近时平仓
    """
    if spread is None:
        return 0, "数据不足"
    
    lower, ma, upper = boll
    
    if z_score > 2.0:
        # 价差高于布林上轨，做空价差（预期回归）
        # 做空long，做多short
        return -1, f"价差{z_score:.2f}>2, 做空价差(空原油多PTA), spread={spread:.4f}"
    
    elif z_score < -2.0:
        # 价差低于布林下轨，做多价差（预期回归）
        # 做多long，做空short
        return 1, f"价差{z_score:.2f}<-2, 做多价差(多原油空PTA), spread={spread:.4f}"
    
    elif abs(z_score) < 0.5:
        # 回归到中性区域，平仓
        return 0, f"价差回归中性, spread={spread:.4f}"
    
    else:
        return 0, f"持有观察, z={z_score:.2f}, spread={spread:.4f}"

# ============ 产业链过滤 ============
def check_industry_filter():
    """
    产业链季节性过滤
    - 冬季(11-2月): 能源需求旺季，原油偏多
    - 夏季(6-8月): 化工需求旺季，PTA偏多
    - 春季(3-5月): 金属需求旺季，铜铝偏多
    """
    month = datetime.datetime.now().month
    
    # 能源旺季判断
    energy_bullish = month in [11, 12, 1, 2]  # 冬季取暖需求
    
    # 化工旺季判断
    chem_bullish = month in [6, 7, 8]  # 夏季出行需求
    
    # 金属旺季判断  
    metal_bullish = month in [3, 4, 5, 9, 10]  # 春秋旺季
    
    return {
        'energy': energy_bullish,
        'chemical': chem_bullish,
        'metal': metal_bullish
    }

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：能源与金属产业链对冲策略")
    print(f"交易对: {list(PAIRS.keys())}")
    
    # 持仓: {pair_key: {'position': 1/-1, 'entry_spread': float, 'entry_long': float, 'entry_short': float}}
    positions = {}
    
    while True:
        try:
            # 获取产业链过滤信号
            industry = check_industry_filter()
            print(f"\n产业链信号: 能源旺季={industry['energy']}, 化工旺季={industry['chemical']}, 金属旺季={industry['metal']}")
            
            # 遍历所有交易对
            for pair_key, pair_config in PAIRS.items():
                spread, boll, z_score = calculate_spread(
                    api, 
                    pair_config['long'], 
                    pair_config['short']
                )
                
                signal, reason = generate_pair_signal(spread, boll, z_score)
                print(f"\n{pair_config['name']}: {reason}")
                
                # 产业链过滤
                if pair_key == "SC_PTA":
                    # 原油-PTA对冲，根据产业链调整
                    if industry['energy'] and industry['chemical']:
                        # 都是旺季，降低仓位
                        signal_factor = 0.5
                    elif industry['energy']:
                        signal_factor = 1.2  # 能源更强
                    elif industry['chemical']:
                        signal_factor = 0.8  # 化工更强
                    else:
                        signal_factor = 1.0
                else:  # CU_AL
                    if industry['metal']:
                        signal_factor = 1.2
                    else:
                        signal_factor = 0.8
                
                # 处理持仓
                if pair_key in positions:
                    pos = positions[pair_key]
                    
                    # 检查止盈止损
                    current_spread = spread
                    if current_spread:
                        # 计算当前盈亏比例
                        pnl_ratio = (current_spread - pos['entry_spread']) / pos['entry_spread']
                        
                        if pnl_ratio < -STOP_LOSS:
                            print(f"[止损] {pair_config['name']} 对冲, pnl={pnl_ratio*100:.1f}%")
                            del positions[pair_key]
                        elif pnl_ratio > 0.03:  # 3%止盈
                            print(f"[止盈] {pair_config['name']} 对冲, pnl={pnl_ratio*100:.1f}%")
                            del positions[pair_key]
                        elif signal == 0 and abs(z_score) < 0.5:
                            print(f"[平仓] {pair_config['name']} 价差回归中性")
                            del positions[pair_key]
                
                # 开仓决策
                if pair_key not in positions and signal != 0:
                    # 获取当前价格
                    long_klines = api.get_kline_serial(pair_config['long'], KLINE_DURATION, data_length=5)
                    short_klines = api.get_kline_serial(pair_config['short'], KLINE_DURATION, data_length=5)
                    
                    if len(long_klines) > 0 and len(short_klines) > 0:
                        long_price = long_klines['close'].iloc[-1]
                        short_price = short_klines['close'].iloc[-1]
                        
                        adjusted_signal = int(signal * signal_factor)
                        
                        positions[pair_key] = {
                            'position': adjusted_signal,
                            'entry_spread': spread,
                            'entry_long': long_price,
                            'entry_short': short_price,
                            'name': pair_config['name']
                        }
                        
                        if adjusted_signal > 0:
                            print(f"[开多价差] {pair_config['name']}: 多{pair_config['long']}, 空{pair_config['short']}")
                        else:
                            print(f"[开空价差] {pair_config['name']}: 空{pair_config['long']}, 多{pair_config['short']}")
            
            api.wait_update(60)  # 每分钟检查一次
            
        except KeyboardInterrupt:
            print("策略停止")
            break
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            api.wait_update(10)

    api.close()

if __name__ == "__main__":
    main()
