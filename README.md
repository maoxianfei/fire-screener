# K线阴阳形态筛选器

全市场A股K线形态匹配 + 量价双规则确认。

## 筛选流程

```
全市场A股 (~5200只)
    │
    ▼
┌─────────────────────────┐
│  一轮：形态扫描           │  K线滑动窗口匹配阴阳形态
│  可选：价格区间预过滤      │
└───────────┬─────────────┘
            │ 命中股票
            ▼
┌─────────────────────────┐
│  二轮：量价双规则 AND     │  放量确认 + 均线确认
└───────────┬─────────────┘
            │ 最终股票池
            ▼
        输出CSV
```

## 快速开始

```bash
# 全流程（一轮+二轮）
python screener.py --pattern 阳阳阴阴阳 --period weekly --start 2025-01-01

# 加价格区间过滤
python screener.py --pattern 阳阳阴阴阳 --period weekly --start 2025-01-01 --price-min 5 --price-max 50

# 只跑一轮
python screener.py --pattern 阳阳阴阴阳 --period weekly --start 2025-01-01 --step 1

# 只跑二轮（指定一轮CSV）
python screener.py --step 2 --input output/一轮_阳阳阴阴阳_weekly_20250101.csv
```

## 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--pattern` | (必填) | 阴阳形态，如 `阳阳阴阴阳` 或 `00101` |
| `--period` | weekly | K线周期: daily/weekly/monthly |
| `--start` | 2025-01-01 | 搜索起始日期 |
| `--end` | 今天 | 搜索结束日期 |
| `--price-min` | 0 | 最低股价过滤 |
| `--price-max` | 9999 | 最高股价过滤 |
| `--workers` | 12 | 并发线程数 |
| `--count` | 自动 | K线数量（默认按日期范围自动计算） |
| `--step` | all | 执行步骤: 1=一轮, 2=二轮, all=全流程 |
| `--input` | — | 二轮输入CSV路径（仅 --step 2 时使用） |

## 阴阳判断规则

`close >= open` → 阳 (1)
`close < open`  → 阴 (0)

## 二轮筛选规则

| 规则 | 条件 | 说明 |
|------|------|------|
| 量 | 最近25天至少1天成交量 > 120日均量 | 放量确认 |
| 价 | 最新收盘价 ≥ 70日均线 × 0.95 | 允许-5%容差 |
| 通过 | 量 ∧ 价 同时满足 | AND逻辑 |

## 项目结构

```
fire-earth/
├── data_fetcher.py   # A股K线拉取 + 股票列表
├── screener.py       # 形态筛选 + 量价规则 + CLI入口
├── output/           # 输出目录
└── README.md
```

## 依赖

```bash
pip install mootdx
```

Python 3.9+
