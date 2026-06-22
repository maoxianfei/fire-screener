# 火地球 (Fire-Earth) — A股全栈选股系统

K线形态全市场扫描 + 主力吸筹识别 + 股票池管理 + 技术分析工具集。

---

## 项目结构

```
fire-screener/
├── screener.py              # 核心：K线阴阳形态全市场扫描器
├── data_fetcher.py          # 数据层：mootdx 获取A股K线数据
├── dual_filter.py           # 二次筛选：周线+日线联合过滤
├── analyze_bottom.py        # 底部形态分析
├── README.md                # 本文件
└── output/                  # 扫描结果输出目录
    ├── 一轮_*.csv           # 一轮形态扫描结果
    ├── 二轮_*.csv           # 二轮量价筛选结果
    ├── 筛选结果_*.png       # 可视化图片
    └── *.json               # 结构化数据
```

关联项目：`~/richard/claude_code/stock-strategy/` — 持仓管理、交易策略、Web面板

---

## 核心工具

### 1. K线形态扫描器 (screener.py)

全市场A股阴阳形态扫描，支持一轮形态匹配 + 二轮量价筛选。

```bash
# 日线形态扫描
python3 screener.py --pattern 1010001 --period daily --start 2026-05-03 --end 2026-06-03 \
  --price-min 24 --price-max 40 --step 1

# 周线形态扫描
python3 screener.py --pattern 001001101010001 --period weekly --price-min 32 --price-max 44 --step 1

# 用K线数量代替日期范围
python3 screener.py --pattern 1010001 --period daily --count 7 --step 1

# 二轮量价筛选
python3 screener.py --step 2 --input output/一轮_xxx.csv
```

形态格式：`1`=阳(涨) `0`=阴(跌)，按K线顺序排列。

### 2. 二次筛选器 (dual_filter.py)

对周线命中的股票，再做日线形态二次过滤。

```bash
python3 dual_filter.py
# 读取周线结果CSV → 检查最近10天日线是否出现指定形态 → 输出交集
```

### 3. 数据层 (data_fetcher.py)

基于 mootdx 库，获取A股K线数据。

```python
from data_fetcher import fetch_klines, fetch_current_prices, get_stock_list

# 获取日线数据
klines = fetch_klines('000001', period='daily', count=120)
# period: 'daily'=日线(9) | 'weekly'=周线(5) | 'monthly'=月线(10)

# 获取当前价格
prices = fetch_current_prices(['000001', '600519'])

# 获取全市场股票列表
stocks = get_stock_list()
```

**⚠️ mootdx 关键参数**：使用 `frequency` 而非 `category`！

| frequency值 | 周期 |
|-------------|------|
| 4 | 1分钟 |
| 5 | 周线 |
| 6 | 月线 |
| 9 | 日线 |
| 10 | 季线 |
| 11 | 年线 |

### 4. 主力吸筹扫描 (full_xichou_scan.py)

全市场主力吸筹信号扫描，支持日/周/月线。

```bash
# 日线吸筹扫描
python3 full_xichou_scan.py --period daily --count 30

# 周线吸筹扫描
python3 full_xichou_scan.py --period weekly --count 12

# 月线吸筹扫描（科创板）
python3 full_xichou_scan.py --period monthly --market 688
```

### 5. 日线形态扫描 (daily_pattern_scan.py)

```bash
python3 daily_pattern_scan.py --pattern 100001 --count 10
```

### 6. 周线形态扫描 (weekly_pattern_scan.py)

```bash
python3 weekly_pattern_scan.py --pattern 100001 --count 7
```

---

## 筛选结果汇总 (2026-05-28 ~ 06-19)

### 日线形态筛选

| 日期 | 形态 | 周期 | 价格区间 | 命中数 | 备注 |
|------|------|------|----------|--------|------|
| 06-03 | 1010001 | 日线7根 | 全市场 | 28只 | 阳阴阳阴阴阴阳，底部试探回升 |
| 06-03 | 001001101010001 | 周线15根 | ¥32-44 | 2只 | 泛微网络、浩辰软件 |
| 06-03 | 100001 | 周线6根 | 全市场 | 198只 | 阳阴阴阴阴阳，四连阴后收阳 |
| 06-04 | 0101101010 | 日线10根 | ¥8-12 | 4只 | 阴阳阴阳阳阴阳阴阳阴，震荡洗盘 |
| 06-09 | 1010001 | 日线7根 | ¥10-20 | 多只 | 低价区扫描 |
| 06-10 | 001011011110001 | 日线15根 | ¥24-40 | 0只 | 形态过长，无精确匹配 |
| 06-18 | 形态扫描 | 月线 | ¥60-100 | 1只 | 帝科股份300842 |

### 周线+日线联合筛选

周线 100001 (199只) → 日线 100001/1010001 二次筛选 → **12只命中**

日线 100001（4只）：ST长方、海宁皮城、第一医药、中海油服
日线 1010001（8只）：齐翔腾达、天原股份、博源化工、海南矿业、鲁西化工、华新建材、云天化、三美股份

### 主力吸筹扫描

| 日期 | 范围 | 结果 |
|------|------|------|
| 06-17 | 长鑫产业链29只 | 6只有吸筹信号（中微公司4次、浪潮信息4次、中科曙光3次、紫光股份3次） |
| 06-19 | 科创板月线 | 18只命中，已入股票池"科创月线吸筹" |
| 06-19 | 日线形态+吸筹 | 多轮扫描，结果存入记忆宫殿 |

### 回购进度调查 (06-14)

股票池"回购"板块20只全部调查完毕：
- ✅ 已完成 8只（40%）：大秦铁路15亿、龙佰集团9亿、新开源3亿...
- 🔄 进行中 12只（60%）：康辰药业78%、赛托生物80%+...
- 博腾股份回购用于**注销减资**，最利好

---

## 股票池管理

股票池文件：`~/richard/claude_code/stock-strategy/stock_pool.json`

| 分组 | 数量 | 说明 |
|------|------|------|
| etf | 20 | ETF标的 |
| 回购 | 20 | 回购概念股 |
| 倍量5x+ | 1 | 倍量突破 |
| 615周线信号火地水雷 | 36 | 周线易经卦象信号 |
| 617吸筹 | 23 | 主力吸筹信号 |
| 持续缩量 | 61 | 持续缩量标的 |
| 长鑫产业链 | 29 | 长鑫存储产业链 |
| 科创周线吸筹 | 61 | 科创板周线吸筹 |
| 科创月线吸筹 | 18 | 科创板月线吸筹（排除医疗生物） |

### 持仓管理

持仓文件：`~/richard/claude_code/stock-strategy/portfolio.json`
当前持仓：13只

Web面板：`~/richard/claude_code/stock-strategy/web/` (端口8080)
- A股/币圈标签页
- 红涨绿跌深色科技风
- 仓位显示：1成/3成/7成

---

## 输出结果可视化

筛选结果可转换为深色科技风格图片：

```python
# 生成HTML → 浏览器截图 → PNG
# 参考 output/result_1010001.html 模板
# 红涨绿跌配色，monospace字体
```

---

## 技术要点

- **数据源**：mootdx (通达信行情接口)
- **形态定义**：close >= open 为阳(1)，否则为阴(0)
- **二轮量价规则**：
  - 最近25天至少1天成交量 > 120日均量
  - 收盘价 ≥ 70日均线 × 0.95
- **RSI算法**：Wilder平滑（非SMA）
- **做空阈值**：100 - 做多阈值
- **macOS注意事项**：禁用SSL验证（mootdx兼容性）

---

## 使用示例

```bash
# 1. 扫描日线形态（最近7天，价格8-12元）
python3 screener.py --pattern 1010001 --period daily --count 7 \
  --price-min 8 --price-max 12 --step 1

# 2. 扫描周线形态
python3 screener.py --pattern 100001 --period weekly --count 7 --step 1

# 3. 周线结果做日线二次筛选
python3 dual_filter.py

# 4. 主力吸筹全市场扫描
python3 full_xichou_scan.py --period daily --count 30

# 5. 科创板月线吸筹
python3 full_xichou_scan.py --period monthly --market 688
```

---

## 更新日志

- **2026-05-28**：项目创建，基础形态扫描器
- **2026-05-29**：多轮形态筛选测试
- **2026-06-03**：二次筛选器(dual_filter.py)，结果可视化(PNG)
- **2026-06-04**：低价股形态扫描
- **2026-06-09~10**：扩展形态测试，15根K线形态验证
- **2026-06-13**：主力吸筹指标集成，倍量筛选
- **2026-06-14**：回购进度调查（20只全部完成）
- **2026-06-15**：周线形态扫描与股票池整合
- **2026-06-16**：MemPalace集成，股票知识存档
- **2026-06-17**：长鑫产业链吸筹扫描（6只信号）
- **2026-06-18**：同有科技技术分析，月线形态扫描
- **2026-06-19**：mootdx参数修复(category→frequency)，科创板月线吸筹18只入池
