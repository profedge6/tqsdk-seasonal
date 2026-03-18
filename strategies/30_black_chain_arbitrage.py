#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
策略30 — 黑色系产业链套利策略
Black Industry Chain Arbitrage Strategy

【策略类型】产业链跨品种套利（均值回归 + 趋势突破双模式）
【适用市场】黑色金属期货（铁矿石、螺纹钢、热卷、焦煤、焦炭、线材）
【核心逻辑】
  基于黑色系产业链逻辑（上中下游关系），捕捉产业链内品种间价差的均值回归机会。
  同时监控布林带突破信号，兼顾趋势行情。
  产业链路径：
    焦煤(JM) → 焦炭(J) → 螺纹钢(RB) / 热卷(HC)
    铁矿石(I) → 螺纹钢(RB) / 热卷(HC)
    螺纹钢(RB) ↔ 热卷(HC)  （替代品套利）

【作者】profedge6
【更新日期】2026-03-18
"""

import sys
import os
import datetime
import math
from tqsdk import TqApi, TqAuth, TqAccount
from tqsdk.tafunc import ma, ema, std, boll, atr

# ==================== 策略参数 ====================
STRATEGY_ID = "30_black_chain_arbitrage"
STRATEGY_NAME = "黑色系产业链套利策略"
STRATEGY_DESC = "焦煤-焦炭-钢材产业链跨品种套利 + 布林带均值回归"

# 产业链套利对配置
# 每对: (symbol_a, symbol_b, ratio_a_to_b, pair_name, chain_direction)
# ratio_a_to_b: 1手A对应多少手B
PAIRS = [
    # 焦煤-焦炭产业链（焦煤 → 焦炭，成本推动逻辑）
    ("KQ.m@DCE.jm", "KQ.m@DCE.j",   1.0, "焦煤-焦炭", "JM→J"),
    # 螺纹钢-热卷（建材产业链，替代品套利）
    ("KQ.m@SHFE.rb", "KQ.m@SHFE.hc", 1.0, "螺纹钢-热卷", "RB-HC"),
    # 铁矿石-螺纹钢（上游-下游产业链）
    ("KQ.m@DCE.i",   "KQ.m@SHFE.rb", 1.0, "铁矿石-螺纹钢", "I→RB"),
    # 焦炭-螺纹钢（综合产业链）
    ("KQ.m@DCE.j",   "KQ.m@SHFE.rb", 1.0, "焦炭-螺纹钢", "J→RB"),
]

# 技术参数
BB_WINDOW = 20          # 布林带窗口
BB_STD = 2.0            # 布林带标准差倍数
ZSCORE_ENTRY = 1.8     # 入场 z-score 阈值
ZSCORE_EXIT = 0.5      # 出场 z_score 阈值
ZSCORE_STOP = 3.0      # 止损 z_score

# 趋势过滤参数
TREND_MA_PERIOD = 60    # 趋势判断 MA 周期
TREND_THRESHOLD = 0.01 # 趋势确认阈值

# 风控参数
MAX_PAIRS_ACTIVE = 2    # 最大同时持有对数
STOP_LOSS_ZSCORE = 3.0  # 止损 z-score
TAKE_PROFIT_ZSCORE = 0.5  # 止盈 z-score
MAX_HOLD_DAYS = 15      # 最大持仓天数

# ==================== 辅助函数 ====================
def normalize_symbol(sym: str) -> str:
    """标准化合约代码"""
    if sym.startswith("KQ.m@"):
        return sym
    if "@" not in sym:
        # 自动补全交易所前缀
        if sym in ["DCE.jm", "DCE.j", "DCE.i"]:
            return f"KQ.m@{sym}"
        elif sym in ["SHFE.rb", "SHFE.hc"]:
            return f"KQ.m@{sym}"
    return sym

def get_kline(api: TqApi, sym: str, length: int = 90):
    """获取K线数据"""
    try:
        kq = api.get_kline_serial(sym, 86400, length)
        return kq
    except Exception:
        return None

def compute_zscore(spread_series, window: int = BB_WINDOW) -> float:
    """计算价差 z-score"""
    if len(spread_series) < window:
        return 0.0
    recent = spread_series.iloc[-window:]
    mean = recent.mean()
    s = recent.std()
    current = spread_series.iloc[-1]
    if s == 0:
        return 0.0
    return (current - mean) / s

def compute_boll_zscore(close_a: list, close_b: list, ratio_a: float, ratio_b: float,
                         window: int = BB_WINDOW) -> dict:
    """计算布林带 + z-score"""
    spread = [(a * ratio_a - b * ratio_b) for a, b in zip(close_a, close_b)]
    spread_series = type('Series', (), {'iloc': lambda self, i: spread[i],
                                         '__len__': lambda self: len(spread),
                                         'mean': lambda self: sum(spread)/len(spread),
                                         'std': lambda self: (sum((x-sum(spread)/len(spread))**2 for x in spread)/len(spread))**0.5})()

    current_spread = spread[-1]
    ma_val = sum(spread[-window:]) / window
    std_val = (sum((x - ma_val)**2 for x in spread[-window:]) / window) ** 0.5

    z = (current_spread - ma_val) / std_val if std_val > 0 else 0

    upper = ma_val + BB_STD * std_val
    lower = ma_val - BB_STD * std_val

    return {
        "zscore": z,
        "spread": current_spread,
        "ma": ma_val,
        "upper": upper,
        "lower": lower,
        "in_band_upper": lower < current_spread < upper,
        "above_upper": current_spread > upper,
        "below_lower": current_spread < lower,
    }

def get_trend_direction(close_arr) -> int:
    """判断价格趋势方向: 1=多头, -1=空头, 0=震荡"""
    if len(close_arr) < TREND_MA_PERIOD:
        return 0
    ma_val = sum(close_arr[-TREND_MA_PERIOD:]) / TREND_MA_PERIOD
    current = close_arr[-1]
    change_pct = (current - ma_val) / ma_val if ma_val > 0 else 0
    if change_pct > TREND_THRESHOLD:
        return 1
    elif change_pct < -TREND_THRESHOLD:
        return -1
    return 0

def get_pair_entry_signal(
    zscore: float,
    direction: str,
    spread: float,
    ma_val: float,
    trend_a: int,
    trend_b: int
) -> dict:
    """
    判断套利对入场信号
    direction: "JM→J" = 做多JM做空J（焦煤涨跌幅 > 焦炭），"J→RB" = 做多J做空RB
    返回: {"action": "long_spread"|"short_spread"|"none", "confidence": 0.0~1.0}
    """
    # z-score > ZSCORE_ENTRY → 价差偏高 → 做空价差（空A多B，预期回归）
    # z-score < -ZSCORE_ENTRY → 价差偏低 → 做多价差（多A空B，预期回归）

    # 趋势过滤：趋势共振时降低信号强度
    trend_conflict = (trend_a == trend_b and trend_a != 0)
    confidence = 0.8 if not trend_conflict else 0.5

    # 布林带确认
    if abs(zscore) > ZSCORE_ENTRY:
        if zscore > ZSCORE_ENTRY:
            # 价差在上轨之外 → 做空价差（期望回归）
            return {"action": "short_spread", "confidence": confidence}
        else:
            # 价差在下轨之外 → 做多价差（期望回归）
            return {"action": "long_spread", "confidence": confidence}

    return {"action": "none", "confidence": 0.0}

def get_pair_exit_signal(zscore: float, holding_direction: str) -> bool:
    """判断是否需要平仓"""
    # 价差回归到均值附近
    if abs(zscore) < ZSCORE_EXIT:
        return True
    # 止损
    if holding_direction == "long_spread" and zscore < -ZSCORE_STOP:
        return True
    if holding_direction == "short_spread" and zscore > ZSCORE_STOP:
        return True
    return False

# ==================== 主逻辑 ====================
def run_strategy(account: TqAccount, is_backtest: bool = True):
    """运行黑色系产业链套利策略"""
    auth = TqAuth(account.user_name, account.password)

    if is_backtest:
        api = TqApi(account, auth, backtest_start_date="2025-01-01", backtest_end_date="2026-03-01")
    else:
        api = TqApi(account, auth)

    print(f"[{STRATEGY_ID}] 策略启动: {STRATEGY_NAME}")
    print(f"[{STRATEGY_ID}] 运行模式: {'回测' if is_backtest else '模拟/实盘'}")
    print(f"[{STRATEGY_ID}] 监控套利对: {[p[3] for p in PAIRS]}")

    # 标准化合约
    normalized_pairs = []
    for a, b, ratio, name, direction in PAIRS:
        na, nb = normalize_symbol(a), normalize_symbol(b)
        normalized_pairs.append((na, nb, ratio, name, direction))

    # 订阅行情
    all_syms = list(set([s for p in normalized_pairs for s in (p[0], p[1])]))
    quotes = {sym: None for sym in all_syms}

    # 持仓状态: {(sym_a, sym_b): {"direction": "long_spread"|"short_spread"|None, "entry_spread": float, "entry_date": date}}
    active_positions = {}
    entry_dates = {}

    last_check_date = None

    with api.register_update_notify():
        while True:
            api.wait_update(deadline=30)
            current_time = datetime.datetime.now()
            trade_date = current_time.date()

            # 更新行情
            for sym in all_syms:
                quotes[sym] = api.get_quote(sym)

            if quotes.get(all_syms[0]) is None:
                continue

            # 每日检查一次
            if last_check_date == trade_date and not is_backtest:
                import time
                time.sleep(60)
                continue
            last_check_date = trade_date

            # 获取K线
            klines = {}
            for sym in all_syms:
                klines[sym] = get_kline(api, sym, 90)

            # 遍历所有套利对
            for sym_a, sym_b, ratio, pair_name, chain_dir in normalized_pairs:
                pair_key = (sym_a, sym_b)

                kq_a = klines.get(sym_a)
                kq_b = klines.get(sym_b)
                if kq_a is None or kq_b is None or len(kq_a) < BB_WINDOW or len(kq_b) < BB_WINDOW:
                    continue

                close_a = list(kq_a.close.iloc[-90:])
                close_b = list(kq_b.close.iloc[-90:])
                high_a = list(kq_a.high.iloc[-90:])
                high_b = list(kq_b.high.iloc[-90:])

                # 计算布林带
                bb_info = compute_boll_zscore(close_a, close_b, ratio, 1.0, BB_WINDOW)
                zscore = bb_info["zscore"]

                # 趋势判断
                trend_a = get_trend_direction(close_a)
                trend_b = get_trend_direction(close_b)

                current_pos = active_positions.get(pair_key, {})

                if current_pos.get("direction") is None:
                    # 无持仓 → 检查入场信号
                    signal = get_pair_entry_signal(
                        zscore, chain_dir,
                        bb_info["spread"], bb_info["ma"],
                        trend_a, trend_b
                    )
                    if signal["action"] != "none" and len(active_positions) < MAX_PAIRS_ACTIVE:
                        direction = signal["action"]
                        price_a = quotes[sym_a].last_price
                        price_b = quotes[sym_b].last_price
                        if price_a and price_b and price_a > 0 and price_b > 0:
                            if direction == "long_spread":
                                # 多A（焦煤/螺纹钢）空B（焦炭/热卷）
                                print(f"[{STRATEGY_ID}] [{pair_name}] 入场做多价差: z={zscore:.2f}, 方向={chain_dir}, confidence={signal['confidence']:.2f}")
                                api.insert_order(sym_a, limit_price=price_a, direction="buy",  offset="open", volume=1)
                                api.insert_order(sym_b, limit_price=price_b, direction="sell", offset="open", volume=1)
                            else:
                                # 空A多B
                                print(f"[{STRATEGY_ID}] [{pair_name}] 入场做空价差: z={zscore:.2f}, 方向={chain_dir}, confidence={signal['confidence']:.2f}")
                                api.insert_order(sym_a, limit_price=price_a, direction="sell", offset="open", volume=1)
                                api.insert_order(sym_b, limit_price=price_b, direction="buy",  offset="open", volume=1)

                            active_positions[pair_key] = {
                                "direction": direction,
                                "entry_spread": bb_info["spread"],
                                "entry_zscore": zscore,
                            }
                            entry_dates[pair_key] = trade_date
                else:
                    # 有持仓 → 检查出场信号
                    direction = current_pos["direction"]
                    entry_date = entry_dates.get(pair_key, trade_date)
                    hold_days = (trade_date - entry_date).days if entry_date else 0

                    should_exit = get_pair_exit_signal(zscore, direction)

                    if should_exit or hold_days >= MAX_HOLD_DAYS:
                        reason = "回归出场" if should_exit else "超时强平"
                        print(f"[{STRATEGY_ID}] [{pair_name}] 出场: {reason}, z={zscore:.2f}, 持仓天数={hold_days}")
                        price_a = quotes[sym_a].last_price
                        price_b = quotes[sym_b].last_price
                        if direction == "long_spread":
                            api.insert_order(sym_a, limit_price=price_a, direction="sell", offset="close", volume=1)
                            api.insert_order(sym_b, limit_price=price_b, direction="buy",  offset="close", volume=1)
                        else:
                            api.insert_order(sym_a, limit_price=price_a, direction="buy",  offset="close", volume=1)
                            api.insert_order(sym_b, limit_price=price_b, direction="sell", offset="close", volume=1)
                        active_positions.pop(pair_key, None)
                        entry_dates.pop(pair_key, None)
                    else:
                        # 记录当前状态（无操作）
                        entry_z = current_pos["entry_zscore"]
                        pnl_z = zscore - entry_z if direction == "long_spread" else entry_z - zscore
                        if trade_date.day % 3 == 0:  # 每3天打印一次状态
                            print(f"[{STRATEGY_ID}] [{pair_name}] 持仓中: z={zscore:.2f}, 持仓天数={hold_days}/{MAX_HOLD_DAYS}, PnL(z)={pnl_z:.2f}")

            if is_backtest and trade_date > datetime.date(2026, 3, 1):
                break

            if not is_backtest:
                import time
                time.sleep(60)

if __name__ == "__main__":
    print("=" * 60)
    print(f"策略 {STRATEGY_ID}: {STRATEGY_NAME}")
    print(f"说明: {STRATEGY_DESC}")
    print("=" * 60)
    ACC = TqAccount("GAD量化实验账户", "profedge6", "")
    run_strategy(ACC, is_backtest=True)
