#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
策略29 — 宏观因子与情绪共振策略
Macro Factor & Sentiment Resonance Strategy

【策略类型】多因子截面 + 宏观周期过滤
【适用市场】商品期货全板块
【核心逻辑】
  结合宏观经济增长预期、美元周期、库存周期与市场情绪四维因子，
  对商品期货各板块进行截面打分，构建多空组合。当因子信号共振时放大仓位。
【作者】profedge6
【更新日期】2026-03-18
"""

import sys
import os
import datetime
from tqsdk import TqApi, TqAuth, TqAccount
from tqsdk.tafunc import ma, ema, std, boll, atr

# ==================== 策略参数 ====================
STRATEGY_ID = "29_macro_sentiment"
STRATEGY_NAME = "宏观因子与情绪共振策略"
STRATEGY_DESC = "宏观经济增长 × 美元周期 × 库存周期 × 市场情绪 四维共振"

# 标的列表（分板块）
SECTIONS = {
    "能源化工": ["KQ.m@INE.sc", "KQ.m@CZCE.TA", "KQ.m@SHFE.bu", "KQ.m@SHFE.fu", "KQ.m@CZCE.MA"],
    "黑色金属": ["KQ.m@SHFE.rb", "KQ.m@SHFE.hc", "KQ.m@DCE.j", "KQ.m@DCE.jm", "KQ.m@DCE.i"],
    "有色金属": ["KQ.m@SHFE.cu", "KQ.m@SHFE.al", "KQ.m@SHFE.zn", "KQ.m@SHFE.pb", "KQ.m@SHFE.ni"],
    "农产品":   ["KQ.m@DCE.m", "KQ.m@DCE.y", "KQ.m@CZCE.CF", "KQ.m@CZCE.SR", "KQ.m@DCE.p"],
}

# 宏观因子配置（模拟宏观数据，实际可对接宏观数据库）
# 1 = 扩张期利好商品，-1 = 收缩期利空商品
# 基于PMI趋势、CRB指数、美元指数的代理变量
USE_HISTORICAL_MODE = True  # True=用历史价格规律推断宏观状态

# 技术参数
MOMENTUM_WINDOW = 20    # 动量窗口（天）
VOLATILITY_WINDOW = 20  # 波动率窗口（天）
SENTIMENT_WINDOW = 10   # 情绪窗口（天）
LOOKBACK = 60           # 回归计算窗口

# 仓位参数
MAX_POSITIONS = 2       # 最大同时持仓
STOP_LOSS_PCT = 0.025   # 止损 2.5%
TAKE_PROFIT_PCT = 0.05  # 止盈 5%
REBALANCE_DAYS = 5      # 调仓周期（交易日）

# ==================== 宏观因子计算 ====================
def get_macro_phase(trade_date: datetime.date) -> int:
    """
    基于历史规律推断当前宏观周期阶段
    返回: 1=扩张期，-1=收缩期，0=中性
    """
    month = trade_date.month

    # 传统宏观周期代理（基于历史经济数据规律）
    # 1-3月: 年初信贷宽松 + 春节后复工，商品需求预期回升
    # 4-6月: 旺季尾声，需求峰值后回落
    # 7-9月: 夏季淡季，高温限产
    # 10-12月: 年末基建赶工，商品需求回升

    # PMI季节性规律（历史均值代理）
    if month in [2, 3, 10, 11]:
        return 1   # 扩张期
    elif month in [6, 7, 8]:
        return -1  # 收缩/淡季
    else:
        return 0   # 中性

def get_usd_cycle(trade_date: datetime.date) -> float:
    """
    模拟美元周期因子（基于季节性规律）
    返回: -1~1（负=美元弱利好商品，正=美元强利空商品）
    """
    month = trade_date.month
    # 美元季节性：年初走弱（美国财政年度换汇），年中走强
    if month in [1, 2, 3]:
        return -0.5
    elif month in [9, 10, 11]:
        return 0.3
    else:
        return 0.0

def get_inventory_cycle(trade_date: datetime.date) -> int:
    """
    库存周期判断（基于历史行业规律）
    返回: 1=主动补库（利好），-1=主动去库（利空），0=中性
    """
    month = trade_date.month
    # 补库季节性（历史均值）
    if month in [3, 4, 5, 10, 11]:
        return 1
    elif month in [7, 8, 9]:
        return -1
    else:
        return 0

def get_sentiment_score(quotes_dict: dict, symbols: list) -> dict:
    """
    计算市场情绪分（基于成交量变化率 + 价格动量）
    返回: {symbol: sentiment_score (-1~1)}
    """
    sentiment = {}
    for sym in symbols:
        try:
            kq = quotes_dict.get(sym)
            if kq is None or len(kq) < SENTIMENT_WINDOW + 5:
                sentiment[sym] = 0.0
                continue
            close_arr = kq.close.iloc[-SENTIMENT_WINDOW:]
            vol_arr = kq.volume.iloc[-SENTIMENT_WINDOW:]

            # 动量（价格变化）
            price_change = (close_arr.iloc[-1] / close_arr.iloc[0] - 1) * 100

            # 成交量变化
            if vol_arr.iloc[0] > 0:
                vol_change = (vol_arr.iloc[-1] / vol_arr.iloc[0] - 1)
            else:
                vol_change = 0

            # 综合情绪分
            s = (price_change * 0.6 + vol_change * 100 * 0.4)
            sentiment[sym] = max(-1, min(1, s / 5))  # 归一化到 [-1, 1]
        except Exception:
            sentiment[sym] = 0.0
    return sentiment

# ==================== 因子打分 ====================
def compute_factor_score(
    quotes_dict: dict,
    sym: str,
    macro_phase: int,
    usd_factor: float,
    inventory_phase: int,
    sentiment: float
) -> float:
    """计算综合因子得分"""
    try:
        kq = quotes_dict.get(sym)
        if kq is None or len(kq) < MOMENTUM_WINDOW + 5:
            return 0.0

        close_arr = kq.close.iloc[-LOOKBACK:]
        high_arr = kq.high.iloc[-LOOKBACK:]
        low_arr = kq.low.iloc[-LOOKBACK:]

        # ---------- 动量因子 ----------
        mom_20 = close_arr.iloc[-1] / close_arr.iloc[-MOMENTUM_WINDOW] - 1
        # Z-score 动量
        mom_mean = close_arr.pct_change().mean()
        mom_std = close_arr.pct_change().std()
        if mom_std > 0:
            mom_z = (mom_20 - mom_mean * MOMENTUM_WINDOW) / (mom_std * (MOMENTUM_WINDOW ** 0.5))
        else:
            mom_z = 0

        # ---------- 波动率因子 ----------
        ret = close_arr.pct_change().dropna()
        vol_20 = ret.iloc[-VOLATILITY_WINDOW:].std() * (252 ** 0.5)
        vol_hist = ret.std() * (252 ** 0.5)
        # 低波动率 → 正分（均值回归）
        if vol_hist > 0:
            vol_z = (vol_20 - vol_hist) / vol_hist
        else:
            vol_z = 0
        vol_score = -vol_z * 0.3  # 低波动加正分

        # ---------- 期限结构因子 ----------
        # MA5 vs MA20，判断 contango/backwardation
        ma5 = ma(kq.close.iloc[-5:].values, 5)[-1]
        ma20 = ma(kq.close.iloc[-20:].values, 20)[-1]
        if ma20 > 0:
            term_structure = (ma5 / ma20 - 1) * 100
        else:
            term_structure = 0
        # Contango (升水) → 供应宽松 → 空头正分；Backwardation → 供应紧张 → 多头正分
        ts_score = -term_structure * 0.2  # contango得负分

        # ---------- 宏观因子 ----------
        macro_score = macro_phase * 0.4 + inventory_phase * 0.3 + usd_factor * (-0.3)

        # ---------- 情绪因子 ----------
        sentiment_score = sentiment * 0.3

        # ---------- 综合得分 ----------
        total = (
            mom_z * 0.35 +
            vol_score * 0.15 +
            ts_score * 0.15 +
            macro_score * 0.20 +
            sentiment_score * 0.15
        )
        return total
    except Exception:
        return 0.0

# ==================== 主逻辑 ====================
def run_strategy(account: TqAccount, is_backtest: bool = True):
    """运行宏观因子与情绪共振策略"""
    auth = TqAuth(account.user_name, account.password)

    if is_backtest:
        api = TqApi(account, auth, backtest_start_date="2025-01-01", backtest_end_date="2026-03-01")
    else:
        api = TqApi(account, auth)

    print(f"[{STRATEGY_ID}] 策略启动: {STRATEGY_NAME}")
    print(f"[{STRATEGY_ID}] 运行模式: {'回测' if is_backtest else '模拟/实盘'}")

    # 展期配置
    all_symbols = []
    for s_list in SECTIONS.values():
        all_symbols.extend(s_list)

    target_symbols = ["KQ.m@" + s.split("@")[1] if "@" in s and "KQ.m@" not in s else s
                      for s in all_symbols]
    unique_syms = list(dict.fromkeys(target_symbols))

    print(f"[{STRATEGY_ID}] 订阅品种数: {len(unique_syms)}")

    quotes = {}
    positions = {}

    last_rebalance_date = None
    trade_days_count = 0

    with api.register_update_notify():
        while True:
            api.wait_update(deadline=30)
            current_time = datetime.datetime.now()
            trade_date = current_time.date()

            # 更新行情
            for sym in unique_syms:
                quotes[sym] = api.get_quote(sym)

            # 每日启动逻辑
            if not quotes.get(unique_syms[0]):
                continue

            # 检查是否需要调仓
            should_rebalance = False
            if last_rebalance_date is None:
                should_rebalance = True
            else:
                prev_close = quotes[unique_syms[0]].datetime
                # 简单按交易日计数
                if trade_days_count >= REBALANCE_DAYS:
                    should_rebalance = True

            if should_rebalance:
                trade_days_count = 0
                last_rebalance_date = trade_date

                # 获取K线数据
                kline_data = {}
                for sym in unique_syms:
                    try:
                        kq = api.get_kline_serial(sym, 86400, 90)
                        kline_data[sym] = kq
                    except Exception:
                        pass

                # 计算宏观因子
                macro_phase = get_macro_phase(trade_date)
                usd_factor = get_usd_cycle(trade_date)
                inventory_phase = get_inventory_cycle(trade_date)
                sentiment_dict = get_sentiment_score(kline_data, unique_syms)

                # 计算所有品种因子得分
                scores = {}
                for sym in unique_syms:
                    if sym in kline_data and len(kline_data[sym]) > LOOKBACK:
                        scores[sym] = compute_factor_score(
                            kline_data, sym,
                            macro_phase, usd_factor,
                            inventory_phase, sentiment_dict.get(sym, 0)
                        )
                    else:
                        scores[sym] = 0.0

                # 排序
                sorted_symbols = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                long_candidates = [s for s, sc in sorted_symbols if sc > 0][:MAX_POSITIONS]
                short_candidates = [s for s, sc in sorted_symbols if sc < 0][-MAX_POSITIONS:]

                # 先平所有现有仓位
                account_pos = api.get_position()
                for sym, pos in account_pos.items():
                    if pos.pos_long != 0 and pos.symbol in unique_syms:
                        print(f"[{STRATEGY_ID}] 平多: {pos.symbol}, 数量: {pos.pos_long}")
                        api.insert_order(pos.symbol, limit_price=quotes[pos.symbol].last_price,
                                         direction="sell", offset="close", volume=pos.pos_long)
                    if pos.pos_short != 0 and pos.symbol in unique_syms:
                        print(f"[{STRATEGY_ID}] 平空: {pos.symbol}, 数量: {pos.pos_short}")
                        api.insert_order(pos.symbol, limit_price=quotes[pos.symbol].last_price,
                                         direction="buy", offset="close", volume=pos.pos_short)

                # 开新仓
                for sym in long_candidates:
                    price = quotes[sym].last_price
                    if price and price > 0:
                        print(f"[{STRATEGY_ID}] 开多: {sym}, 得分: {scores[sym]:.3f}, 价: {price}")
                        api.insert_order(sym, limit_price=price,
                                         direction="buy", offset="open", volume=1)

                for sym in short_candidates:
                    price = quotes[sym].last_price
                    if price and price > 0:
                        print(f"[{STRATEGY_ID}] 开空: {sym}, 得分: {scores[sym]:.3f}, 价: {price}")
                        api.insert_order(sym, limit_price=price,
                                         direction="sell", offset="open", volume=1)

                print(f"[{STRATEGY_ID}] 宏观因子: 扩张期={macro_phase}, 美元={usd_factor:.2f}, 库存={inventory_phase}")
                print(f"[{STRATEGY_ID}] 本轮多: {long_candidates}, 空: {short_candidates}")

            # 止损/止盈风控（逐tick检查）
            account_pos = api.get_position()
            for sym, pos in account_pos.items():
                if sym not in unique_syms:
                    continue
                entry_price = pos.open_price_long if pos.pos_long > 0 else pos.open_price_short
                current_price = quotes.get(sym)
                if current_price is None or entry_price <= 0:
                    continue
                current_pnl_pct = (current_price.last_price - entry_price) / entry_price if pos.pos_long > 0 \
                    else (entry_price - current_price.last_price) / entry_price

                if current_pnl_pct <= -STOP_LOSS_PCT:
                    print(f"[{STRATEGY_ID}] 触发止损: {sym}, 亏损: {current_pnl_pct*100:.2f}%")
                    direction = "sell" if pos.pos_long > 0 else "buy"
                    offset = "close"
                    api.insert_order(sym, limit_price=current_price.last_price,
                                     direction=direction, offset=offset, volume=pos.pos_long + pos.pos_short)
                elif current_pnl_pct >= TAKE_PROFIT_PCT:
                    print(f"[{STRATEGY_ID}] 触发止盈: {sym}, 盈利: {current_pnl_pct*100:.2f}%")
                    direction = "sell" if pos.pos_long > 0 else "buy"
                    offset = "close"
                    api.insert_order(sym, limit_price=current_price.last_price,
                                     direction=direction, offset=offset, volume=pos.pos_long + pos.pos_short)

            trade_days_count += 1

            if is_backtest and trade_date > datetime.date(2026, 3, 1):
                break

            if not is_backtest:
                import time
                time.sleep(60)

if __name__ == "__main__":
    # 默认回测模式
    print("=" * 60)
    print(f"策略 {STRATEGY_ID}: {STRATEGY_NAME}")
    print(f"说明: {STRATEGY_DESC}")
    print("=" * 60)
    ACC = TqAccount("GAD量化实验账户", "profedge6", "")
    run_strategy(ACC, is_backtest=True)
