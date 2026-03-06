"""
================================================================================
策略编号: 13
策略名称: 白糖季节性策略（Sugar Seasonal Strategy）
生成日期: 2026-03-06
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
白糖期货是中国期货市场中最具农产品特性的品种之一，其价格走势受到全球食糖市场
供需格局、巴西甘蔗产区天气、季风季节以及国内消费旺季等多重因素影响，呈现出
明显的季节性规律。本策略基于以下核心市场规律构建：

【一、巴西榨季过渡期（3月-4月）做空白糖】
巴西是全球最大的食糖生产国和出口国，其甘蔗榨季通常从每年4月开始持续到11月。
3-4月处于新旧榨季交替阶段，巴西食糖库存处于年度高位水平，同时新榨季刚开始
生产，供应压力较大。此外，3月通常是国内白糖消费淡季，库存累积明显。
历史数据显示，3-4月白糖价格往往面临下行压力。

做空条件：
  - 当前月份在 [3, 4] 范围内（旧榨季库存高峰/新榨季初期）
  - 5日均线下穿20日均线（死叉信号，确认下行趋势）
  - RSI(14) 低于60（避免追空超卖市场）
  - 成交量较20日均量放大（确认趋势有效性）

【二、夏季消费旺季（6月-8月）做多白糖】
6-8月正值夏季饮料消费高峰，白糖作为食品工业原料需求旺盛。同时，6月开始
巴西新榨季生产逐渐明朗，如出现产能不及预期或港口物流延误的情况，会推动
国际糖价上涨。国内白糖市场在夏季也进入传统消费旺季，下游补库需求增加。

做多条件：
  - 当前月份在 [6, 7, 8] 范围内（夏季消费旺季）
  - 5日均线上穿20日均线（金叉信号，确认上行趋势）
  - RSI(14) 高于40（避免追多超买市场）
  - 成交量较20日均量放大（确认趋势有效性）

【三、持仓与风控管理】
  - 每次开仓固定1手白糖主力合约
  - 止损：开仓价格的 1.5%
  - 止盈：开仓价格的 4.0%
  - 持仓超过 20 个交易日强制平仓
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
        logging.FileHandler("13_sugar_seasonal.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================
# 策略参数配置
# ============================================================
# 交易标的：郑商所白糖主力合约
SYMBOL = "KQ.m@CZCE.SR"       # 白糖主力连续合约（自动跟踪主力）
EXCHANGE = "CZCE"

# 季节性窗口配置
# 巴西榨季过渡期：3-4月，做空白糖
SHORT_MONTHS = [3, 4]
# 夏季消费旺季：6-8月，做多白糖
LONG_MONTHS = [6, 7, 8]

# 技术指标参数
MA_SHORT = 5                   # 短期均线周期
MA_LONG = 20                   # 长期均线周期
RSI_PERIOD = 14                # RSI周期
RSI_OVERBOUGHT = 60            # RSI超买阈值
RSI_OVERSOLD = 40              # RSI超卖阈值

# 风控参数
POSITION_SIZE = 1              # 每次开仓手数
STOP_LOSS_PCT = 0.015          # 止损比例 1.5%
TAKE_PROFIT_PCT = 0.040        # 止盈比例 4.0%
MAX_HOLD_DAYS = 20             # 最大持仓天数

# ============================================================
# 策略信号计算
# ============================================================
def calculate_signals(kline):
    """计算技术指标和交易信号"""
    closes = kline["close"]
    
    # 计算均线
    ma5 = ma(closes, MA_SHORT)
    ma20 = ma(closes, MA_LONG)
    
    # 计算RSI
    rsi_val = rsi(closes, RSI_PERIOD)
    
    # 计算成交量均线
    volumes = kline["volume"]
    vol_ma20 = ma(volumes, 20)
    
    return {
        "ma5": ma5,
        "ma20": ma20,
        "rsi": rsi_val,
        "volume": volumes[-1] if len(volumes) > 0 else 0,
        "vol_ma20": vol_ma20[-1] if len(vol_ma20) > 0 else 0,
        "close": closes[-1] if len(closes) > 0 else 0,
    }

def check_seasonal_window(current_month):
    """检查当前是否处于季节性交易窗口"""
    is_short_window = current_month in SHORT_MONTHS
    is_long_window = current_month in LONG_MONTHS
    return is_short_window, is_long_window

def generate_signal(signals, current_month):
    """根据技术信号和季节性窗口生成交易信号"""
    if signals is None:
        return "NONE"
    
    ma5 = signals["ma5"]
    ma20 = signals["ma20"]
    rsi_val = signals["rsi"]
    volume = signals["volume"]
    vol_ma20 = signals["vol_ma20"]
    
    # 检查是否在季节性窗口
    is_short_window, is_long_window = check_seasonal_window(current_month)
    
    # 成交量放大确认
    volume_confirmed = volume > vol_ma20 * 1.2 if vol_ma20 > 0 else False
    
    # 做空信号：季节性窗口 + 死叉 + RSI不过于超卖 + 成交量放大
    if is_short_window and len(ma5) >= 2 and len(ma20) >= 2:
        if ma5[-1] < ma20[-1] and ma5[-2] >= ma20[-2]:  # 死叉
            if rsi_val < RSI_OVERBOUGHT and volume_confirmed:
                return "SHORT"
    
    # 做多信号：季节性窗口 + 金叉 + RSI不过于超买 + 成交量放大
    if is_long_window and len(ma5) >= 2 and len(ma20) >= 2:
        if ma5[-1] > ma20[-1] and ma5[-2] <= ma20[-2]:  # 金叉
            if rsi_val > RSI_OVERSOLD and volume_confirmed:
                return "LONG"
    
    return "NONE"

# ============================================================
# 风险检查
# ============================================================
def check_risk(api, position):
    """检查账户风险状态"""
    account = api.get_account()
    positions = api.get_position(SYMBOL)
    
    # 检查持仓盈亏
    if positions["pos_long"] > 0:
        avg_price = positions["avg_long_open_price"]
        current_price = positions["last_price"]
        pnl_pct = (current_price - avg_price) / avg_price
        
        # 止损检查
        if pnl_pct < -STOP_LOSS_PCT:
            logger.warning(f"触发止损: 亏损 {pnl_pct*100:.2f}%")
            return "STOP_LOSS"
        
        # 止盈检查
        if pnl_pct > TAKE_PROFIT_PCT:
            logger.info(f"触发止盈: 盈利 {pnl_pct*100:.2f}%")
            return "TAKE_PROFIT"
    
    elif positions["pos_short"] > 0:
        avg_price = positions["avg_short_open_price"]
        current_price = positions["last_price"]
        pnl_pct = (avg_price - current_price) / avg_price
        
        # 止损检查
        if pnl_pct < -STOP_LOSS_PCT:
            logger.warning(f"触发止损: 亏损 {pnl_pct*100:.2f}%")
            return "STOP_LOSS"
        
        # 止盈检查
        if pnl_pct > TAKE_PROFIT_PCT:
            logger.info(f"触发止盈: 盈利 {pnl_pct*100:.2f}%")
            return "TAKE_PROFIT"
    
    return "NONE"

# ============================================================
# 主策略
# ============================================================
def run_strategy(api):
    """执行白糖季节性策略"""
    logger.info("启动白糖季节性策略...")
    
    # 获取K线数据
    kline = api.get_kline_serial(SYMBOL, 24 * 3600, data_length=100)
    
    position = None
    entry_date = None
    entry_price = 0
    
    while True:
        current_time = datetime.datetime.now()
        current_month = current_time.month
        
        # 同步最新行情
        api.wait_update()
        
        # 每天收盘时检查信号
        if api.is_changing(kline[-1], "datetime"):
            signals = calculate_signals(kline)
            signal = generate_signal(signals, current_month)
            
            positions = api.get_position(SYMBOL)
            has_long = positions["pos_long"] > 0
            has_short = positions["pos_short"] > 0
            
            # 获取持仓信息
            if has_long or has_short:
                risk_signal = check_risk(api, position)
                hold_days = (current_time - entry_date).days if entry_date else 0
                
                # 检查是否需要强制平仓
                if risk_signal in ["STOP_LOSS", "TAKE_PROFIT"] or hold_days > MAX_HOLD_DAYS:
                    # 平仓
                    if has_long:
                        api.close_long(SYMBOL, POSITION_SIZE)
                        logger.info(f"平多仓: {risk_signal}, 持仓天数: {hold_days}")
                    if has_short:
                        api.close_short(SYMBOL, POSITION_SIZE)
                        logger.info(f"平空仓: {risk_signal}, 持仓天数: {hold_days}")
                    position = None
                    entry_date = None
            
            # 开仓信号
            if signal == "LONG" and not has_long and not has_short:
                api.open_long(SYMBOL, POSITION_SIZE)
                position = "LONG"
                entry_date = current_time
                entry_price = signals["close"]
                logger.info(f"开多仓: 价格 {entry_price}, 月份 {current_month}")
                
            elif signal == "SHORT" and not has_short and not has_long:
                api.open_short(SYMBOL, POSITION_SIZE)
                position = "SHORT"
                entry_date = current_time
                entry_price = signals["close"]
                logger.info(f"开空仓: 价格 {entry_price}, 月份 {current_month}")
            
            # 非季节性窗口强制平仓
            if not (current_month in SHORT_MONTHS or current_month in LONG_MONTHS):
                if has_long:
                    api.close_long(SYMBOL, POSITION_SIZE)
                    logger.info("非季节性窗口，平多仓")
                    position = None
                if has_short:
                    api.close_short(SYMBOL, POSITION_SIZE)
                    logger.info("非季节性窗口，平空仓")
                    position = None

# ============================================================
# 策略入口
# ============================================================
if __name__ == "__main__":
    import sys
    
    # 判断运行模式
    if len(sys.argv) > 1 and sys.argv[1] == "backtest":
        # 回测模式
        logger.info("运行回测模式...")
        api = TqApi(auth=TqAuth("demo", "demo"), backtest=TqBacktest(start_dt="2023-01-01", end_dt="2024-12-31"))
        try:
            run_strategy(api)
        except BacktestFinished:
            logger.info("回测完成")
            account = api.get_account()
            logger.info(f"最终权益: {account['balance']:.2f}")
        api.close()
    else:
        # 实盘/模拟交易模式
        logger.info("运行实盘/模拟模式...")
        # 使用天勤模拟账户或实盘账户
        api = TqApi(auth=TqAuth("demo", "demo"))  # 替换为您的账户
        try:
            run_strategy(api)
        except KeyboardInterrupt:
            logger.info("策略停止")
        api.close()
