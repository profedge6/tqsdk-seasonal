"""
================================================================================
策略编号: 01
策略名称: 大豆种植季节性策略（Soybean Seasonal Strategy）
生成日期: 2026-03-02
仓库地址: profedge6/tqsdk-seasonal
================================================================================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【TqSdk 简介】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TqSdk（天勤量化 SDK）是由信易科技开发的专业期货量化交易框架，完全免费开源，
支持 Python 3.6+ 环境。TqSdk 提供对国内各大期货交易所（上期所 SHFE、大商所 DCE、
郑商所 CZCE、中金所 CFFEX、能源中心 INE、广期所 GFEX）的统一数据接口和实盘/模拟
交易接口，具备以下核心特性：

1. **实时行情**：通过天勤服务器实时推送 Tick 数据和 K 线数据，延迟极低；
2. **历史数据**：支持获取任意周期 K 线（秒/分/时/日/周等），数据质量高；
3. **策略开发**：提供同步式 API，代码逻辑清晰，无需处理回调地狱；
4. **回测框架**：内置 BacktestFinished 异常机制，支持策略快速回测验证；
5. **账户管理**：支持多账户并发、组合持仓、资金划拨等企业级功能；
6. **风控模块**：内置持仓限额、资金使用率等风控参数；
7. **社区生态**：拥有活跃的量化社区和丰富的策略模板资源。

官网: https://www.shinnytech.com/tianqin/
文档: https://doc.shinnytech.com/tqsdk/latest/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【策略逻辑说明】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
大豆属于全球农产品市场中最重要的油料作物之一，其价格走势深受种植/收割季节周期
影响，并在每年特定时段呈现出显著的季节性规律。本策略基于以下核心市场规律构建：

【一、南美大豆上市压力期（4月-6月）做空豆粕】
南美（巴西、阿根廷）大豆通常在每年12月至次年3月种植并于3-6月集中收割上市。
4月起南美新豆大量流向全球市场，压制国际大豆价格，并通过贸易传导影响国内豆粕
期货价格（DCE.m）。历史数据显示，4-6月豆粕价格在南美丰收年份通常面临较大的
下行压力，是季节性做空的较优窗口。

做空条件：
  - 当前月份在 [4, 5, 6] 范围内（南美新豆上市压力期）
  - 5日均线下穿20日均线（死叉信号，确认下行趋势）
  - RSI(14) 低于55（避免追空超卖市场）
  - 成交量较20日均量放大（确认趋势有效性）

【二、美豆新作炒作期（10月-11月）做多豆粕】
美国大豆通常在9-11月集中收割，但市场在此前（8-10月）往往会对美豆新作产量预期
进行炒作。当美豆单产预期低于历史均值、或产区天气出现干旱威胁时，市场会推动大豆
价格上涨，并带动国内豆粕期货跟涨。10-11月美豆收割基本完成，市场将视线转向
南美种植进度，如种植进度偏慢则维持偏多格局。

做多条件：
  - 当前月份在 [10, 11] 范围内（美豆新作炒作/南美种植期）
  - 5日均线上穿20日均线（金叉信号，确认上行趋势）
  - RSI(14) 高于45（避免追多超买市场）
  - 成交量较20日均量放大（确认趋势有效性）

【三、持仓与风控管理】
  - 每次开仓固定1手豆粕主力合约
  - 止损：开仓价格的 1.5%
  - 止盈：开仓价格的 4.0%
  - 持仓超过 15 个交易日强制平仓
  - 非季节性窗口期强制平仓清零
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ============================================================
# 导入必要的库
# ============================================================
import datetime
import logging
from tqsdk import TqApi, TqAuth, TqBacktest, BacktestFinished
from tqsdk.tafunc import ma, rsi

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("01_soybean_seasonal.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# 策略参数配置
# ============================================================
# 交易标的：大商所豆粕主力合约
SYMBOL = "KQ.m@DCE.m"         # 豆粕主力连续合约（自动跟踪主力）
EXCHANGE = "DCE"

# 季节性窗口配置
# 南美大豆上市压力期：4-6月，做空豆粕
SHORT_MONTHS = [4, 5, 6]
# 美豆新作炒作期：10-11月，做多豆粕
LONG_MONTHS = [10, 11]

# 技术指标参数
SHORT_MA = 5          # 短期均线周期（日线）
LONG_MA = 20          # 长期均线周期（日线）
RSI_PERIOD = 14       # RSI 计算周期
RSI_SHORT_MAX = 55    # 做空时 RSI 上限（避免追空超卖后的反弹）
RSI_LONG_MIN = 45     # 做多时 RSI 下限（避免追多超买后的回调）
VOLUME_RATIO = 1.2    # 成交量放大倍数（相对20日均量）

# 风控参数
TRADE_VOLUME = 1      # 每次开仓手数
STOP_LOSS_PCT = 0.015 # 止损比例 1.5%
TAKE_PROFIT_PCT = 0.04 # 止盈比例 4.0%
MAX_HOLD_DAYS = 15    # 最大持仓天数

# ============================================================
# 季节判断函数
# ============================================================
def get_season_signal(month: int) -> str:
    """
    根据当前月份返回季节性信号。

    参数:
        month: 当前月份 (1-12)

    返回值:
        'SHORT'  - 南美大豆上市压力期，倾向做空豆粕
        'LONG'   - 美豆新作炒作期，倾向做多豆粕
        'NEUTRAL'- 非季节性窗口，保持观望
    """
    if month in SHORT_MONTHS:
        logger.info(f"当前月份 {month} 月 → 进入南美大豆上市压力期，做空窗口开启")
        return "SHORT"
    elif month in LONG_MONTHS:
        logger.info(f"当前月份 {month} 月 → 进入美豆新作炒作期，做多窗口开启")
        return "LONG"
    else:
        logger.info(f"当前月份 {month} 月 → 非季节性窗口期，保持观望")
        return "NEUTRAL"


# ============================================================
# 技术指标过滤函数
# ============================================================
def check_short_signal(klines) -> bool:
    """
    检查做空技术信号是否成立。

    判断条件（需全部满足）：
    1. MA5 < MA20（死叉，短期均线下穿长期均线）
    2. 前一根K线 MA5 >= MA20（确认是刚发生的死叉，非持续空头）
    3. RSI(14) < RSI_SHORT_MAX（避免追空超卖区域）
    4. 当日成交量 > 20日均量 * VOLUME_RATIO（成交量放大确认）

    参数:
        klines: TqSdk K线数据对象（日线）

    返回值:
        True  - 做空信号成立
        False - 做空信号不成立
    """
    # 计算均线
    ma5_series = ma(klines.close, SHORT_MA)
    ma20_series = ma(klines.close, LONG_MA)

    # 获取最新两根K线的均线值
    ma5_curr = ma5_series.iloc[-1]
    ma5_prev = ma5_series.iloc[-2]
    ma20_curr = ma20_series.iloc[-1]
    ma20_prev = ma20_series.iloc[-2]

    # 计算RSI
    rsi_series = rsi(klines.close, RSI_PERIOD)
    rsi_curr = rsi_series.iloc[-1]

    # 计算成交量均值
    vol_curr = klines.volume.iloc[-1]
    vol_ma20 = klines.volume.iloc[-20:].mean()

    # 死叉信号检测
    death_cross = (ma5_curr < ma20_curr) and (ma5_prev >= ma20_prev)
    # RSI 过滤
    rsi_filter = rsi_curr < RSI_SHORT_MAX
    # 成交量过滤
    volume_filter = vol_curr > vol_ma20 * VOLUME_RATIO

    logger.debug(
        f"做空信号检测 → MA5={ma5_curr:.2f}, MA20={ma20_curr:.2f}, "
        f"死叉={death_cross}, RSI={rsi_curr:.2f}, 量比={vol_curr/vol_ma20:.2f}"
    )

    return death_cross and rsi_filter and volume_filter


def check_long_signal(klines) -> bool:
    """
    检查做多技术信号是否成立。

    判断条件（需全部满足）：
    1. MA5 > MA20（金叉，短期均线上穿长期均线）
    2. 前一根K线 MA5 <= MA20（确认是刚发生的金叉，非持续多头）
    3. RSI(14) > RSI_LONG_MIN（避免追多超买区域）
    4. 当日成交量 > 20日均量 * VOLUME_RATIO（成交量放大确认）

    参数:
        klines: TqSdk K线数据对象（日线）

    返回值:
        True  - 做多信号成立
        False - 做多信号不成立
    """
    # 计算均线
    ma5_series = ma(klines.close, SHORT_MA)
    ma20_series = ma(klines.close, LONG_MA)

    # 获取最新两根K线的均线值
    ma5_curr = ma5_series.iloc[-1]
    ma5_prev = ma5_series.iloc[-2]
    ma20_curr = ma20_series.iloc[-1]
    ma20_prev = ma20_series.iloc[-2]

    # 计算RSI
    rsi_series = rsi(klines.close, RSI_PERIOD)
    rsi_curr = rsi_series.iloc[-1]

    # 计算成交量均值
    vol_curr = klines.volume.iloc[-1]
    vol_ma20 = klines.volume.iloc[-20:].mean()

    # 金叉信号检测
    golden_cross = (ma5_curr > ma20_curr) and (ma5_prev <= ma20_prev)
    # RSI 过滤
    rsi_filter = rsi_curr > RSI_LONG_MIN
    # 成交量过滤
    volume_filter = vol_curr > vol_ma20 * VOLUME_RATIO

    logger.debug(
        f"做多信号检测 → MA5={ma5_curr:.2f}, MA20={ma20_curr:.2f}, "
        f"金叉={golden_cross}, RSI={rsi_curr:.2f}, 量比={vol_curr/vol_ma20:.2f}"
    )

    return golden_cross and rsi_filter and volume_filter


# ============================================================
# 主策略函数
# ============================================================
def run_strategy():
    """
    大豆种植季节性策略主函数。

    策略执行流程：
    1. 初始化 TqSdk API 连接（可切换回测/实盘）
    2. 订阅豆粕主力合约日线 K 线数据
    3. 进入主循环，每次 K 线更新时执行策略逻辑：
       a. 判断当前月份季节性信号
       b. 若在季节性窗口内，检测技术指标信号
       c. 满足条件则开仓，否则检查止盈/止损/强平条件
       d. 非窗口期强制清仓
    4. 回测完成后输出统计信息
    """

    # ----------------------------------------------------------
    # 初始化 API
    # 实盘时替换为：api = TqApi(TqAuth("用户名", "密码"))
    # 回测模式：指定起止日期
    # ----------------------------------------------------------
    try:
        api = TqApi(
            backtest=TqBacktest(
                start_dt=datetime.date(2020, 1, 1),
                end_dt=datetime.date(2025, 12, 31),
            ),
            auth=TqAuth("tq_seasonal_demo", "demo_password"),  # 替换为实际账号
        )
    except Exception as e:
        logger.error(f"API 初始化失败: {e}")
        logger.info("提示：请替换 TqAuth 中的账号密码，或使用模拟账号运行")
        return

    # ----------------------------------------------------------
    # 订阅行情数据
    # 获取豆粕主力合约最近250根日线（用于计算技术指标）
    # ----------------------------------------------------------
    klines = api.get_kline_serial(SYMBOL, 86400, data_length=250)  # 86400秒 = 1天
    quote = api.get_quote(SYMBOL)
    logger.info(f"行情订阅成功，标的: {SYMBOL}")

    # ----------------------------------------------------------
    # 持仓状态跟踪变量
    # ----------------------------------------------------------
    position = api.get_position(SYMBOL)
    entry_price = 0.0          # 开仓价格
    entry_date = None          # 开仓日期
    hold_days = 0              # 持仓天数计数器
    last_bar_id = -1           # 上一根K线ID（用于判断新K线生成）

    logger.info("=" * 60)
    logger.info("策略启动：大豆种植季节性策略")
    logger.info(f"做空窗口月份: {SHORT_MONTHS}")
    logger.info(f"做多窗口月份: {LONG_MONTHS}")
    logger.info(f"止损比例: {STOP_LOSS_PCT*100:.1f}%")
    logger.info(f"止盈比例: {TAKE_PROFIT_PCT*100:.1f}%")
    logger.info(f"最大持仓天数: {MAX_HOLD_DAYS}")
    logger.info("=" * 60)

    try:
        while True:
            # 等待数据更新
            api.wait_update()

            # --------------------------------------------------
            # 仅在新的日线K线生成时执行策略逻辑（避免重复触发）
            # --------------------------------------------------
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue

            current_bar_id = klines.iloc[-1]["id"]
            if current_bar_id == last_bar_id:
                continue
            last_bar_id = current_bar_id

            # --------------------------------------------------
            # 获取当前日期信息
            # --------------------------------------------------
            bar_dt = datetime.datetime.fromtimestamp(
                klines.iloc[-1]["datetime"] / 1e9
            )
            current_month = bar_dt.month
            current_price = klines.iloc[-1]["close"]

            logger.info(f"\n{'─'*50}")
            logger.info(f"日期: {bar_dt.strftime('%Y-%m-%d')}  收盘价: {current_price:.0f}")

            # --------------------------------------------------
            # 获取当前持仓量（正数=多头，负数=空头，0=无持仓）
            # --------------------------------------------------
            net_pos = position.pos_long - position.pos_short

            # --------------------------------------------------
            # 获取季节性信号
            # --------------------------------------------------
            season_signal = get_season_signal(current_month)

            # ==================================================
            # 情形一：当前有持仓，检查平仓条件
            # ==================================================
            if net_pos != 0:
                hold_days += 1
                profit_pct = (current_price - entry_price) / entry_price

                # 空头持仓时收益方向相反
                if net_pos < 0:
                    profit_pct = -profit_pct

                logger.info(
                    f"当前持仓: {'多' if net_pos > 0 else '空'}{abs(net_pos)}手  "
                    f"持仓天数: {hold_days}  浮动盈亏: {profit_pct*100:.2f}%"
                )

                should_close = False
                close_reason = ""

                # 1. 止盈检查
                if profit_pct >= TAKE_PROFIT_PCT:
                    should_close = True
                    close_reason = f"止盈触发（收益率 {profit_pct*100:.2f}% >= {TAKE_PROFIT_PCT*100:.1f}%）"

                # 2. 止损检查
                elif profit_pct <= -STOP_LOSS_PCT:
                    should_close = True
                    close_reason = f"止损触发（亏损率 {abs(profit_pct)*100:.2f}% >= {STOP_LOSS_PCT*100:.1f}%）"

                # 3. 超时平仓检查
                elif hold_days >= MAX_HOLD_DAYS:
                    should_close = True
                    close_reason = f"持仓超时（已持 {hold_days} 天，超过 {MAX_HOLD_DAYS} 天限制）"

                # 4. 非季节窗口强制平仓（多头在非做多月、空头在非做空月）
                elif net_pos > 0 and season_signal != "LONG":
                    should_close = True
                    close_reason = "季节性窗口结束，多头强制平仓"
                elif net_pos < 0 and season_signal != "SHORT":
                    should_close = True
                    close_reason = "季节性窗口结束，空头强制平仓"

                # 执行平仓
                if should_close:
                    logger.info(f"平仓信号: {close_reason}")
                    if net_pos > 0:
                        # 平多仓
                        api.insert_order(
                            symbol=SYMBOL,
                            direction="SELL",
                            offset="CLOSE",
                            volume=abs(net_pos),
                        )
                        logger.info(f"执行平多: {abs(net_pos)}手，参考价 {current_price:.0f}")
                    else:
                        # 平空仓
                        api.insert_order(
                            symbol=SYMBOL,
                            direction="BUY",
                            offset="CLOSE",
                            volume=abs(net_pos),
                        )
                        logger.info(f"执行平空: {abs(net_pos)}手，参考价 {current_price:.0f}")

                    # 重置持仓追踪变量
                    entry_price = 0.0
                    entry_date = None
                    hold_days = 0

            # ==================================================
            # 情形二：当前无持仓，检查开仓条件
            # ==================================================
            else:
                # 确保K线数据足够计算指标（至少需要LONG_MA+5根K线）
                if len(klines) < LONG_MA + 5:
                    logger.info(f"K线数据不足（当前{len(klines)}根，需要{LONG_MA+5}根），跳过")
                    continue

                if season_signal == "SHORT":
                    # ------------------------------------------
                    # 南美大豆上市压力期：尝试开空
                    # ------------------------------------------
                    if check_short_signal(klines):
                        api.insert_order(
                            symbol=SYMBOL,
                            direction="SELL",
                            offset="OPEN",
                            volume=TRADE_VOLUME,
                        )
                        entry_price = current_price
                        entry_date = bar_dt
                        hold_days = 0
                        logger.info(
                            f"✅ 开空成功: {TRADE_VOLUME}手  "
                            f"参考价 {current_price:.0f}  "
                            f"止损价 {current_price * (1 + STOP_LOSS_PCT):.0f}  "
                            f"止盈价 {current_price * (1 - TAKE_PROFIT_PCT):.0f}"
                        )
                    else:
                        logger.info("做空信号未触发，等待下一个机会")

                elif season_signal == "LONG":
                    # ------------------------------------------
                    # 美豆新作炒作期：尝试开多
                    # ------------------------------------------
                    if check_long_signal(klines):
                        api.insert_order(
                            symbol=SYMBOL,
                            direction="BUY",
                            offset="OPEN",
                            volume=TRADE_VOLUME,
                        )
                        entry_price = current_price
                        entry_date = bar_dt
                        hold_days = 0
                        logger.info(
                            f"✅ 开多成功: {TRADE_VOLUME}手  "
                            f"参考价 {current_price:.0f}  "
                            f"止损价 {current_price * (1 - STOP_LOSS_PCT):.0f}  "
                            f"止盈价 {current_price * (1 + TAKE_PROFIT_PCT):.0f}"
                        )
                    else:
                        logger.info("做多信号未触发，等待下一个机会")

                else:
                    # 非季节窗口期：保持空仓观望
                    logger.info("非季节窗口期，保持空仓观望")

    except BacktestFinished:
        # ----------------------------------------------------------
        # 回测结束，输出统计摘要
        # ----------------------------------------------------------
        logger.info("\n" + "=" * 60)
        logger.info("回测完成！策略统计摘要：")
        logger.info(f"  标的合约: {SYMBOL}")
        logger.info(f"  做空窗口: {SHORT_MONTHS} 月（南美大豆上市压力期）")
        logger.info(f"  做多窗口: {LONG_MONTHS} 月（美豆新作炒作期）")
        logger.info(f"  止损比例: {STOP_LOSS_PCT*100:.1f}%")
        logger.info(f"  止盈比例: {TAKE_PROFIT_PCT*100:.1f}%")
        logger.info(f"  最大持仓: {MAX_HOLD_DAYS} 天")
        logger.info("=" * 60)
        api.close()

    except Exception as e:
        logger.error(f"策略运行异常: {e}", exc_info=True)
        api.close()
        raise


# ============================================================
# 程序入口
# ============================================================
if __name__ == "__main__":
    logger.info("大豆种植季节性策略（01_soybean_seasonal.py）启动")
    run_strategy()
