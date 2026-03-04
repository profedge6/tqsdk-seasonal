"""
================================================================================
策略编号: 02
策略名称: 春节前后资金面策略（Spring Festival Liquidity Strategy）
生成日期: 2026-03-02
仓库地址: profedge6/tqsdk-seasonal
================================================================================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【TqSdk 简介】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TqSdk（天勤量化 SDK）是由信易科技（北京）有限公司开发的专业期货量化交易框架，
完全免费开源（Apache 2.0 协议），基于 Python 语言设计，支持 Python 3.6+ 环境。
TqSdk 已服务于数万名国内期货量化投资者，是国内使用最广泛的期货量化框架之一。

TqSdk 核心能力包括：

1. **统一行情接口**：对接国内全部7大期货交易所（SHFE/DCE/CZCE/CFFEX/INE/GFEX）
   及主要期权品种，统一的 get_quote / get_kline_serial 接口，告别繁琐的协议适配；

2. **高性能数据推送**：天勤服务器行情推送延迟通常在5ms以内，Tick 级数据实时到达，
   K线自动合并，支持自定义周期（秒/分钟/小时/日/周/月）；

3. **同步式编程范式**：独特的 wait_update() + is_changing() 设计，策略代码像
   写普通Python一样自然流畅，无需掌握异步编程，大幅降低开发门槛；

4. **完整回测引擎**：内置 TqBacktest 回测模式，历史数据精确到Tick级别，
   支持滑点、手续费等真实市场参数，回测结果可信度高；

5. **实盘/模拟一键切换**：代码结构不变，仅替换 TqApi 初始化参数即可从
   模拟盘切换至实盘，极大降低策略上线风险；

6. **多账户并发**：支持同时连接多个期货账户，适合机构投资者和量化团队；

7. **活跃生态**：官方提供策略示例库、在线文档、量化社区论坛，更新维护活跃。

官网: https://www.shinnytech.com/tianqin/
文档: https://doc.shinnytech.com/tqsdk/latest/
GitHub: https://github.com/shinnytech/tqsdk-python
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【策略逻辑说明】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
春节是中国最重要的传统节日，对金融市场尤其是商品期货市场具有显著而独特的
季节性影响。本策略基于以下两个核心宏观规律构建：

【一、春节前流动性收紧 -> 做空商品期货（螺纹钢rb）】

每年临近春节（通常在农历12月下旬至正月初一前），市场资金面会出现以下特征：
  (1) 企业集中发放年终奖、工资，大量资金从金融系统流向实体经济
  (2) 央行虽通过逆回购、MLF等工具投放流动性，但资金利率通常仍偏紧
  (3) 部分期货持仓者在节前主动减仓，以降低春节期间持仓风险
  (4) 建筑施工进入停工状态，螺纹钢现货需求断崖式下降
  (5) 贸易商年前清库存，现货价格承压

上述因素叠加，历史上春节前1周（5个交易日）螺纹钢期货通常面临较大的下行
压力，是季节性做空的优质时间窗口。

做空触发条件：
  - 当前日期处于春节前第 PRE_FESTIVAL_DAYS 个交易日内
  - 尚无空头持仓（避免重复开仓）

【二、春节后资金回流 -> 做多商品期货（螺纹钢rb）】

春节长假结束后，市场通常出现以下变化：
  (1) 被压抑的消费需求集中释放，经济活动快速恢复
  (2) 建筑施工复工带动建材需求快速升温，螺纹钢现货补库需求增加
  (3) 节前流出的资金陆续回流至金融体系，资金面转松
  (4) 市场情绪从保守转向乐观，风险偏好上升
  (5) 节后首个交易日往往出现"开门红"效应，多头资金集中入场

历史数据显示，春节后首个交易日至第3个交易日（持有3天），螺纹钢期货往往
出现明显上涨，是捕捉节后行情的黄金窗口。

做多触发条件：
  - 当前为春节后第一个交易日（当日日期等于 POST_FESTIVAL_START_DATE）
  - 尚无多头持仓（避免重复开仓）

【三、持仓管理与风控】
  - 做空持仓：持有 PRE_FESTIVAL_DAYS 个交易日后平仓（或春节前最后一天强平）
  - 做多持仓：持有 POST_HOLD_DAYS 个交易日后平仓
  - 止损：开仓价格的 STOP_LOSS_PCT
  - 止盈：开仓价格的 TAKE_PROFIT_PCT

【四、春节日期数据库】
由于中国春节日期每年不同（农历正月初一对应公历日期不同），策略内置了
2020-2030年的春节日期数据，并自动计算节前交易日（倒推）和节后首个交易日。
实际使用时，建议维护最新年度数据。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ============================================================
# 导入必要的库
# ============================================================
import datetime
import logging
from tqsdk import TqApi, TqAuth, TqBacktest, BacktestFinished

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("02_spring_festival_effect.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# 策略参数配置
# ============================================================
# 交易标的：上海期货交易所螺纹钢主力合约
SYMBOL = "KQ.m@SHFE.rb"       # 螺纹钢主力连续合约（自动跟踪主力）

# 春节效应参数
PRE_FESTIVAL_DAYS = 5         # 节前做空窗口（节前第几个交易日开始做空）
POST_HOLD_DAYS = 3            # 节后做多持有天数（持有3个交易日）

# 风控参数
TRADE_VOLUME = 1              # 每次开仓手数
STOP_LOSS_PCT = 0.015         # 止损比例 1.5%
TAKE_PROFIT_PCT = 0.035       # 止盈比例 3.5%

# ============================================================
# 春节日期数据库（公历）
# 格式: {年份: {"new_year": 农历正月初一公历日期, "holiday_end": 节后首个交易日}}
# 说明: holiday_end 通常为正月初八左右（春节假期结束后首个工作日）
# ============================================================
SPRING_FESTIVAL_DB = {
    2020: {
        "new_year": datetime.date(2020, 1, 25),    # 庚子年正月初一
        "holiday_end": datetime.date(2020, 2, 3),  # 春节假期后首个交易日
    },
    2021: {
        "new_year": datetime.date(2021, 2, 12),    # 辛丑年正月初一
        "holiday_end": datetime.date(2021, 2, 18), # 春节假期后首个交易日
    },
    2022: {
        "new_year": datetime.date(2022, 2, 1),     # 壬寅年正月初一
        "holiday_end": datetime.date(2022, 2, 7),  # 春节假期后首个交易日
    },
    2023: {
        "new_year": datetime.date(2023, 1, 22),    # 癸卯年正月初一
        "holiday_end": datetime.date(2023, 1, 28), # 春节假期后首个交易日
    },
    2024: {
        "new_year": datetime.date(2024, 2, 10),    # 甲辰年正月初一
        "holiday_end": datetime.date(2024, 2, 19), # 春节假期后首个交易日
    },
    2025: {
        "new_year": datetime.date(2025, 1, 29),    # 乙巳年正月初一
        "holiday_end": datetime.date(2025, 2, 5),  # 春节假期后首个交易日
    },
    2026: {
        "new_year": datetime.date(2026, 2, 17),    # 丙午年正月初一
        "holiday_end": datetime.date(2026, 2, 25), # 春节假期后首个交易日（预估）
    },
    2027: {
        "new_year": datetime.date(2027, 2, 6),     # 丁未年正月初一
        "holiday_end": datetime.date(2027, 2, 14), # 春节假期后首个交易日（预估）
    },
    2028: {
        "new_year": datetime.date(2028, 1, 26),    # 戊申年正月初一
        "holiday_end": datetime.date(2028, 2, 3),  # 春节假期后首个交易日（预估）
    },
    2029: {
        "new_year": datetime.date(2029, 2, 13),    # 己酉年正月初一
        "holiday_end": datetime.date(2029, 2, 21), # 春节假期后首个交易日（预估）
    },
    2030: {
        "new_year": datetime.date(2030, 2, 3),     # 庚戌年正月初一
        "holiday_end": datetime.date(2030, 2, 11), # 春节假期后首个交易日（预估）
    },
}


# ============================================================
# 辅助函数：获取当年春节相关日期
# ============================================================
def get_festival_dates(year: int) -> dict:
    """
    获取指定年份的春节关键日期。

    参数:
        year: 年份（整数）

    返回值:
        包含以下键的字典：
        - new_year: 农历正月初一对应的公历日期
        - holiday_end: 春节假期结束后的首个交易日
        - pre_window_start: 节前做空窗口开始日期（估算）
        - pre_window_end: 节前最后一天（正月初一前一天）

    注意：pre_window_start 为估算值，实际应根据交易所公布的交易日历确定。
    由于回测环境下无法调用实时交易日历，此处使用自然日近似估算，
    生产环境建议使用 TqSdk 的交易日历接口精确计算。
    """
    if year not in SPRING_FESTIVAL_DB:
        logger.warning(f"年份 {year} 不在春节数据库中，策略将跳过该年份的节假日操作")
        return {}

    data = SPRING_FESTIVAL_DB[year]
    new_year_dt = data["new_year"]
    holiday_end_dt = data["holiday_end"]

    # 估算节前做空窗口开始日期
    # 春节假期通常为7天（正月初一至初七），节前PRE_FESTIVAL_DAYS个交易日
    # 近似以 new_year 前推 (PRE_FESTIVAL_DAYS + 2) 个自然日作为窗口开始信号日
    # 注意：自然日估算，实盘应改用精确交易日历
    pre_window_approx = new_year_dt - datetime.timedelta(days=PRE_FESTIVAL_DAYS + 2)
    pre_window_end = new_year_dt - datetime.timedelta(days=1)

    result = {
        "new_year": new_year_dt,
        "holiday_end": holiday_end_dt,
        "pre_window_start": pre_window_approx,
        "pre_window_end": pre_window_end,
    }

    logger.debug(
        f"{year}年春节数据: 正月初一={new_year_dt}, "
        f"节后首日={holiday_end_dt}, "
        f"节前做空窗口={pre_window_approx}~{pre_window_end}"
    )
    return result


def is_pre_festival_window(current_date: datetime.date, festival_dates: dict) -> bool:
    """
    判断当前日期是否处于春节前做空窗口期。

    参数:
        current_date: 当前K线对应日期
        festival_dates: get_festival_dates() 返回的字典

    返回值:
        True  - 当前日期在节前做空窗口内（pre_window_start 到 pre_window_end）
        False - 不在窗口内
    """
    if not festival_dates:
        return False

    pre_start = festival_dates.get("pre_window_start")
    pre_end = festival_dates.get("pre_window_end")

    if pre_start and pre_end:
        return pre_start <= current_date <= pre_end
    return False


def is_post_festival_first_day(current_date: datetime.date, festival_dates: dict) -> bool:
    """
    判断当前日期是否为春节后首个交易日（做多开仓信号日）。

    参数:
        current_date: 当前K线对应日期
        festival_dates: get_festival_dates() 返回的字典

    返回值:
        True  - 当前日期等于节后首个交易日（holiday_end）
        False - 不是
    """
    if not festival_dates:
        return False

    holiday_end = festival_dates.get("holiday_end")
    if holiday_end:
        return current_date == holiday_end
    return False


# ============================================================
# 主策略函数
# ============================================================
def run_strategy():
    """
    春节前后资金面策略主函数。

    策略执行流程：
    1. 初始化 TqSdk API（回测模式，可替换为实盘）
    2. 订阅螺纹钢主力合约日线 K 线数据
    3. 进入主循环，每根日线执行以下逻辑：
       a. 查询当年春节关键日期（带年度缓存优化）
       b. 判断是否在节前做空窗口 -> 开空螺纹钢
       c. 判断是否为节后首个交易日 -> 开多螺纹钢
       d. 检查已有持仓的止盈/止损/超时平仓条件
    4. 回测结束后输出汇总统计信息
    """

    # ----------------------------------------------------------
    # 初始化 API（回测模式）
    # 实盘时替换为: api = TqApi(TqAuth("用户名", "密码"))
    # ----------------------------------------------------------
    try:
        api = TqApi(
            backtest=TqBacktest(
                start_dt=datetime.date(2020, 1, 1),
                end_dt=datetime.date(2025, 12, 31),
            ),
            auth=TqAuth("tq_festival_demo", "demo_password"),  # 替换为实际账号
        )
    except Exception as e:
        logger.error(f"API 初始化失败: {e}")
        logger.info("提示：请替换 TqAuth 中的账号密码，或使用模拟账号运行")
        return

    # ----------------------------------------------------------
    # 订阅行情数据（日线K线）
    # ----------------------------------------------------------
    klines = api.get_kline_serial(SYMBOL, 86400, data_length=60)  # 最近60根日线
    quote = api.get_quote(SYMBOL)
    logger.info(f"行情订阅成功，标的: {SYMBOL}")

    # ----------------------------------------------------------
    # 持仓状态跟踪变量
    # ----------------------------------------------------------
    position = api.get_position(SYMBOL)
    entry_price = 0.0           # 开仓价格
    entry_date = None           # 开仓日期
    hold_days = 0               # 已持仓天数（开仓次日起计数）
    last_bar_id = -1            # 上一根K线ID，用于判断是否有新K线生成
    current_year_festival = {}  # 当前年度春节日期缓存
    cached_year = -1            # 已缓存的年份

    logger.info("=" * 60)
    logger.info("策略启动：春节前后资金面策略")
    logger.info(f"标的合约  : {SYMBOL}")
    logger.info(f"节前做空  : 春节前 {PRE_FESTIVAL_DAYS} 个交易日内开空")
    logger.info(f"节后做多  : 节后首个交易日开多，持有 {POST_HOLD_DAYS} 天")
    logger.info(f"止损比例  : {STOP_LOSS_PCT*100:.1f}%")
    logger.info(f"止盈比例  : {TAKE_PROFIT_PCT*100:.1f}%")
    logger.info("=" * 60)

    try:
        while True:
            # 等待行情更新
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
            # 获取当前日期与价格信息
            # --------------------------------------------------
            bar_dt = datetime.datetime.fromtimestamp(
                klines.iloc[-1]["datetime"] / 1e9
            )
            current_date = bar_dt.date()
            current_price = klines.iloc[-1]["close"]
            current_year = current_date.year

            logger.info(f"\n{'─'*50}")
            logger.info(f"日期: {current_date}  收盘价: {current_price:.0f}")

            # --------------------------------------------------
            # 按年度更新春节日期缓存（避免每根K线都重新查询）
            # --------------------------------------------------
            if current_year != cached_year:
                current_year_festival = get_festival_dates(current_year)
                cached_year = current_year
                if current_year_festival:
                    logger.info(
                        f"加载 {current_year} 年春节数据: "
                        f"正月初一={current_year_festival['new_year']}, "
                        f"节后首日={current_year_festival['holiday_end']}, "
                        f"节前窗口={current_year_festival['pre_window_start']}"
                        f"~{current_year_festival['pre_window_end']}"
                    )
                else:
                    logger.warning(f"{current_year} 年春节数据未找到，跳过该年节假日策略")

            # --------------------------------------------------
            # 获取当前持仓量（正数=多头，负数=空头，0=无持仓）
            # --------------------------------------------------
            net_pos = position.pos_long - position.pos_short

            # ==================================================
            # 情形一：当前有持仓，检查平仓条件
            # ==================================================
            if net_pos != 0:
                hold_days += 1
                profit_pct = (current_price - entry_price) / entry_price

                # 空头持仓时收益方向相反（价格下跌才盈利）
                if net_pos < 0:
                    profit_pct = -profit_pct

                logger.info(
                    f"当前持仓: {'多' if net_pos > 0 else '空'}{abs(net_pos)}手  "
                    f"持仓天数: {hold_days}  浮动盈亏: {profit_pct*100:.2f}%  "
                    f"开仓价: {entry_price:.0f}"
                )

                should_close = False
                close_reason = ""

                # 1. 止盈检查
                if profit_pct >= TAKE_PROFIT_PCT:
                    should_close = True
                    close_reason = (
                        f"止盈触发（盈利 {profit_pct*100:.2f}% "
                        f">= {TAKE_PROFIT_PCT*100:.1f}%）"
                    )

                # 2. 止损检查
                elif profit_pct <= -STOP_LOSS_PCT:
                    should_close = True
                    close_reason = (
                        f"止损触发（亏损 {abs(profit_pct)*100:.2f}% "
                        f">= {STOP_LOSS_PCT*100:.1f}%）"
                    )

                # 3. 空头：节前窗口到期或进入节后，强制平仓
                elif net_pos < 0:
                    if hold_days >= PRE_FESTIVAL_DAYS:
                        should_close = True
                        close_reason = f"节前空头到期平仓（已持 {hold_days} 天）"
                    elif (current_year_festival and
                          current_date >= current_year_festival.get(
                              "holiday_end", datetime.date(9999, 1, 1))):
                        should_close = True
                        close_reason = "春节结束，节前空头强制平仓"

                # 4. 多头：持有 POST_HOLD_DAYS 个交易日后平仓
                elif net_pos > 0:
                    if hold_days >= POST_HOLD_DAYS:
                        should_close = True
                        close_reason = (
                            f"节后多头到期平仓（已持 {hold_days} 天，"
                            f"目标 {POST_HOLD_DAYS} 天）"
                        )

                # 执行平仓操作
                if should_close:
                    logger.info(f"平仓信号: {close_reason}")
                    if net_pos > 0:
                        # 平多仓：卖出平仓
                        api.insert_order(
                            symbol=SYMBOL,
                            direction="SELL",
                            offset="CLOSE",
                            volume=abs(net_pos),
                        )
                        logger.info(
                            f"[平多] 执行: {abs(net_pos)}手  "
                            f"参考价 {current_price:.0f}  "
                            f"盈亏 {profit_pct*100:.2f}%"
                        )
                    else:
                        # 平空仓：买入平仓
                        api.insert_order(
                            symbol=SYMBOL,
                            direction="BUY",
                            offset="CLOSE",
                            volume=abs(net_pos),
                        )
                        logger.info(
                            f"[平空] 执行: {abs(net_pos)}手  "
                            f"参考价 {current_price:.0f}  "
                            f"盈亏 {profit_pct*100:.2f}%"
                        )

                    # 重置持仓追踪变量
                    entry_price = 0.0
                    entry_date = None
                    hold_days = 0

            # ==================================================
            # 情形二：当前无持仓，检查开仓条件
            # ==================================================
            else:
                if not current_year_festival:
                    logger.debug(f"{current_year}年春节数据缺失，跳过开仓判断")
                    continue

                # ------------------------------------------
                # 信号A：春节前做空窗口 -> 开空螺纹钢
                # 逻辑：春节前资金收紧 + 建筑业停工 + 现货需求下降
                # ------------------------------------------
                if is_pre_festival_window(current_date, current_year_festival):
                    days_to_new_year = (
                        current_year_festival["new_year"] - current_date
                    ).days
                    logger.info(
                        f"[春节前效应] 进入节前做空窗口！"
                        f"距正月初一还有 {days_to_new_year} 天"
                    )
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="OPEN",
                        volume=TRADE_VOLUME,
                    )
                    entry_price = current_price
                    entry_date = current_date
                    hold_days = 0
                    logger.info(
                        f"[开空] 成功: {TRADE_VOLUME}手  "
                        f"参考价 {current_price:.0f}  "
                        f"止损价 {current_price * (1 + STOP_LOSS_PCT):.0f}  "
                        f"止盈价 {current_price * (1 - TAKE_PROFIT_PCT):.0f}  "
                        f"计划持有 {PRE_FESTIVAL_DAYS} 天"
                    )

                # ------------------------------------------
                # 信号B：春节后首个交易日 -> 开多螺纹钢
                # 逻辑：资金回流 + 复工需求 + 节后乐观情绪
                # ------------------------------------------
                elif is_post_festival_first_day(current_date, current_year_festival):
                    logger.info(
                        f"[春节后效应] 节后首个交易日！"
                        f"资金回流+复工效应，开多螺纹钢"
                        f"（日期: {current_date}）"
                    )
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="OPEN",
                        volume=TRADE_VOLUME,
                    )
                    entry_price = current_price
                    entry_date = current_date
                    hold_days = 0
                    logger.info(
                        f"[开多] 成功: {TRADE_VOLUME}手  "
                        f"参考价 {current_price:.0f}  "
                        f"止损价 {current_price * (1 - STOP_LOSS_PCT):.0f}  "
                        f"止盈价 {current_price * (1 + TAKE_PROFIT_PCT):.0f}  "
                        f"计                        f"划持有 {POST_HOLD_DAYS} 天"
                    )

                else:
                    # 非触发日期，记录距离春节的天数
                    new_year_dt = current_year_festival.get("new_year")
                    holiday_end_dt = current_year_festival.get("holiday_end")
                    if new_year_dt:
                        days_to_new_year = (new_year_dt - current_date).days
                        if 0 < days_to_new_year <= 30:
                            logger.info(
                                f"距春节（正月初一）还有 {days_to_new_year} 天，"
                                f"等待节前做空窗口（窗口开始日: "
                                f"{current_year_festival['pre_window_start']}）"
                            )
                        elif holiday_end_dt:
                            days_to_end = (holiday_end_dt - current_date).days
                            if 0 < days_to_end <= 10:
                                logger.info(
                                    f"节后首个交易日还有 {days_to_end} 天，"
                                    f"等待节后做多信号（{holiday_end_dt}）"
                                )
                            else:
                                logger.info("非春节效应窗口期，保持空仓观望")
                        else:
                            logger.info("非春节效应窗口期，保持空仓观望")
                    else:
                        logger.info("非春节效应窗口期，保持空仓观望")

    except BacktestFinished:
        # ----------------------------------------------------------
        # 回测结束，输出统计摘要
        # ----------------------------------------------------------
        logger.info("\n" + "=" * 60)
        logger.info("回测完成！策略统计摘要：")
        logger.info(f"  标的合约  : {SYMBOL}")
        logger.info(f"  节前做空  : 春节前 {PRE_FESTIVAL_DAYS} 个交易日内开空，资金收紧+停工效应")
        logger.info(f"  节后做多  : 节后首日开多，持有 {POST_HOLD_DAYS} 天，资金回流+复工效应")
        logger.info(f"  止损比例  : {STOP_LOSS_PCT*100:.1f}%")
        logger.info(f"  止盈比例  : {TAKE_PROFIT_PCT*100:.1f}%")
        logger.info(f"  春节年份  : {sorted(SPRING_FESTIVAL_DB.keys())}")
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
    logger.info("春节前后资金面策略（02_spring_festival_effect.py）启动")
    run_strategy()
