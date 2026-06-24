# Fire-Screener — A股全栈选股系统

K线形态全市场扫描 + 主力吸筹识别 + 放量突破 + 三重过滤 + 技术分析工具集。

原项目名 **fire-earth**，已统一合并至此目录。

---

## 快速开始

### 统一入口 (CLI)

```bash
cd ~/claude_code/fire-screener
python run.py <scanner> [options]

# 可用扫描器一览
python run.py daily-pattern --pattern 101000 --lookback 30
python run.py weekly-pattern --pattern 101000
python run.py volume-breakout --max-range-ratio 1.15
python run.py 10x-volume --ratio-threshold 10
python run.py xichou --frequency 4 --count 150
python run.py tech-decline --days 20
python run.py tech-volume-decline              # 技术面+量能同步衰退
python run.py triple-filter                    # 三重过滤（日线+周线+量能）
python run.py weekly-zhuli-filter              # 周线主力资金过滤
python run.py full-xichou                      # 全量吸筹扫描
python run.py help                             # 查看所有扫描器
```

### 编程式调用

```python
from run import scan
results = scan('daily-pattern', pattern='101000', market='688')
```

### 直接使用底层模块

```python
from base import fetch_klines, zhuli_xichou, get_stock_list
df = fetch_klines('sh600519', count=150)
df = zhuli_xichou(df)
stocks = get_stock_list(market='688')
```

### 旧版单体扫描器 (保留)

```bash
python screener.py --pattern 1010001 --period daily --count 7 --price-min 8 --price-max 12 --step 1
python dual_filter.py                    # 周线→日线二次筛选
python analyze_bottom.py                 # 底部形态分析
```

---

## 项目结构

```
fire-screener/
│
├── run.py                  # 统一入口（CLI + 编程式 API）
├── base.py                 # 共享基础设施（客户端、数据、指标、扫描框架、输出）
│
├── daily_pattern_scan.py   # 日线形态筛选
├── weekly_pattern_scan.py  # 周线形态筛选
├── volume_breakout.py      # 横盘放量突破
├── volume_10x_scan.py      # 10倍放量
├── full_xichou_scan.py     # 主力吸筹
├── triple_filter.py        # 三重过滤（周线+吸筹+倍量）
├── weekly_zhuli_filter.py  # 周线+吸筹双重过滤
├── tech_volume_decline.py  # 技术面+量能同步衰退
│
├── screener.py             # [旧] K线阴阳形态全市场扫描器
├── data_fetcher.py         # [旧] 数据层：mootdx 获取A股K线数据
├── dual_filter.py          # [旧] 二次筛选：周线+日线联合过滤
├── analyze_bottom.py       # [旧] 底部形态分析
│
├── .gitignore
├── README.md
└── output/                 # 扫描结果（CSV + JSON + HTML）
    └── archive/            # 旧版扫描结果归档
```

---

## 市场过滤

`market` 参数支持：

| 参数 | 范围 |
|------|------|
| `all` | 全市场 |
| `sh` | 沪市 |
| `sz` | 深市 |
| `688` | 科创板 |
| `30` | 创业板 |
| `60` | 沪主板 |
| `00` | 深主板 |

---

## 技术要点

- **数据源**：mootdx (通达信行情接口)
- **形态定义**：`close >= open` 为阳(1)，否则为阴(0)
- **A股颜色**：红涨绿跌
- **RSI算法**：Wilder平滑（非SMA）
- **二轮量价规则**：最近25天至少1天成交量 > 120日均量；收盘价 ≥ 70日均线 × 0.95
- **mootdx frequency 参数**：4=1分钟, 5=周线, 6=月线, 9=日线, 10=季线, 11=年线
- **macOS注意事项**：禁用SSL验证（mootdx兼容性）

## 关键设计

- mootdx 客户端通过 `threading.local()` 实现线程安全，默认 20 并发
- 股票代码格式：`sh600519` / `sz000001`
- 输出到 `output/` 目录（CSV + JSON）

## 依赖

- Python 3.14+
- pandas, numpy
- mootdx (通达信行情接口)

---

## 关联项目

- `~/claude_code/stock-strategy/` — 股票池管理、回测、主力吸筹/出货指标
- `~/claude_code/trading-advisor/` — 交易推荐系统（短线个股+长线ETF轮动）
- `~/richard/claude_code/stock-strategy/web/` — 监控大屏Web面板（端口8080）
