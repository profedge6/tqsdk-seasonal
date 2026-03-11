# tqsdk-seasonal

> 基于 **TqSdk** 的季节性交易策略集合，持续更新中。

## 项目简介

本仓库专注于**季节性交易策略**，利用农产品、能源等品种的季节性规律进行交易。  
所有策略使用 [天勤量化 TqSdk](https://github.com/shinnytech/tqsdk-python) 实现，可直接对接实盘账户。

## 策略列表

| # | 策略名称 | 类型 | 品种 | 文件 |
|---|---------|------|------|------|
| 01 | 大豆季节性策略 | 季节性 | CZCE.a | [01_soybean_seasonal.py](strategies/01_soybean_seasonal.py) |
| 02 | 春节效应策略 | 季节性 | 多品种 | [02_spring_festival_effect.py](strategies/02_spring_festival_effect.py) |
| 03 | 棉花季节性策略 | 季节性 | CZCE.cf | [03_cotton_seasonal.py](strategies/03_cotton_seasonal.py) |
| 04 | 节假日效应策略 | 季节性 | 多品种 | [04_holiday_effect.py](strategies/04_holiday_effect.py) |
| 05 | 原油季节性策略 | 季节性 | SC | [05_crude_oil_seasonal.py](strategies/05_crude_oil_seasonal.py) |
| 06 | 螺纹钢季节性策略 | 季节性 | SHFE.rb | [06_rb_seasonal.py](strategies/06_rb_seasonal.py) |
| 07 | 橡胶季节性策略 | 季节性 | SHFE.ru | [07_ta_seasonal.py](strategies/07_ta_seasonal.py) |
| 08 | 橡胶（RU）季节性策略 | 季节性 | SHFE.ru | [08_ru_seasonal.py](strategies/08_ru_seasonal.py) |
| 09 | 取暖油季节性策略 | 季节性 | CU | [09_heating_oil_seasonal.py](strategies/09_heating_oil_seasonal.py) |
| 10 | 豆粕季节性策略 | 季节性 | DCE.m | [10_soybean_meal_seasonal.py](strategies/10_soybean_meal_seasonal.py) |
| 11 | 黄金季节性策略 | 季节性 | AU | [11_gold_seasonal.py](strategies/11_gold_seasonal.py) |
| 12 | 螺纹钢季节性策略 | 季节性 | SHFE.rb | [12_rb_seasonal.py](strategies/12_rb_seasonal.py) |
| 13 | 白糖季节性策略 | 季节性 | CZCE.sr | [13_sugar_seasonal.py](strategies/13_sugar_seasonal.py) |
| 14 | 棕榈油季节性策略 | 季节性 | DCE.p | [14_palm_oil_seasonal.py](strategies/14_palm_oil_seasonal.py) |
| 15 | 玉米季节性策略 | 季节性 | DCE.c | [15_corn_seasonal.py](strategies/15_corn_seasonal.py) |
| 16 | 小麦季节性策略 | 季节性 | PM | [16_wheat_seasonal.py](strategies/16_wheat_seasonal.py) |
| 17 | 白银季节性策略 | 季节性 | AG | [17_silver_seasonal.py](strategies/17_silver_seasonal.py) |
| 18 | 铜季节性策略 | 季节性 | CU | [18_copper_seasonal.py](strategies/18_copper_seasonal.py) |
| 19 | 铝季节性策略 | 季节性 | AL | [19_aluminum_seasonal.py](strategies/19_aluminum_seasonal.py) |
| 20 | 锌季节性策略 | 季节性 | ZN | [20_zinc_seasonal.py](strategies/20_zinc_seasonal.py) |

## 策略分类

### 🌾 农产品季节性
大豆、棉花、白糖、玉米等农产品受种植周期、收获季节影响。

### 🛢️ 能源季节性
原油、取暖油等受季节性需求变化影响。

### 🥇 金属季节性
黄金、白银、铜金属的季节等有色性规律。

### 🎏 节假日效应
春节、国庆等重大节假日前后的特殊行情。

## 环境要求

```bash
pip install tqsdk numpy pandas
```

## 使用说明

1. 替换代码中 `YOUR_ACCOUNT` / `YOUR_PASSWORD` 为你的天勤账号
2. 根据季节性规律选择合适品种
3. 建议结合基本面分析使用

## 风险提示

- 季节性规律可能随市场变化而改变
- 极端事件可能导致季节性失效
- 本仓库策略仅供学习研究，不构成投资建议

---

**持续更新中，欢迎 Star ⭐ 关注**

*更新时间：2026-03-11*
