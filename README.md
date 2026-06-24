# Fire-Screener — A股技术指标工具集

K线阴阳形态匹配 + 主力吸筹/出货识别 + 成交量异动检测。

---

## 快速开始

### 指标脚本直接调用

```bash
cd ~/claude_code/fire-screener

# K线形态匹配（默认全卦象扫描）
python 指标/kline_pattern.py --code sz000970

# 指定形态搜索
python 指标/kline_pattern.py 101000 --code sz000970

# 主力吸筹
python 指标/zhuli_xichou.py 000970 --period daily

# 主力出货
python 指标/zhuli_chuhuo.py 000970 --period weekly

# 量能异动（默认±30%）
python 指标/volume.py anomaly --code sz000970

# 横盘放量突破
python 指标/volume.py breakout --code sz000970
```

### 编程式调用

```python
# 指标导入
from 指标.kline_pattern import match_pattern, multi_pattern_match
from 指标.zhuli_xichou import zhuli_xichou, fetch_kline
from 指标.zhuli_chuhuo import zhuli_chuhuo
from 指标.volume import check_volume_breakout, check_volume_anomaly

# 获取数据并计算
df = fetch_kline('sh600519', count=150, frequency=4)   # 日线
df = zhuli_xichou(df)                                    # 吸筹指标
signals = df[df['zlxc_jinchang'] > 0]                    # 进场信号
```

### 基础设施

```python
from base import fetch_klines, get_stock_list, scan_all, save_results

# 获取股票列表
stocks = get_stock_list(market='688')

# 全市场扫描框架
results, total = scan_all(stocks, check_fn, workers=20)

# 保存结果
save_results(results, "扫描结果", csv_columns=[...])
```

---

## 项目结构

```
fire-screener/
│
├── 指标/                          # 📁 基础指标库（核心）
│   ├── kline_pattern.py          #     K线阴阳形态匹配 + 预设卦象
│   ├── zhuli_xichou.py           #     主力吸筹（进场/洗盘）
│   ├── zhuli_chuhuo.py           #     主力出货（出货/承接）
│   └── volume.py                 #     成交量（放量突破 + 量能异动）
│
├── base.py                       # 共享基础设施
│   ├── get_client()              #   线程安全 mootdx 客户端
│   ├── get_stock_list()          #   股票列表
│   ├── fetch_klines()            #   K线数据获取
│   ├── zhuli_xichou()            #   吸筹指标（兼容旧版）
│   ├── sma()                     #   通达信 SMA 递推
│   ├── scan_all()                #   全市场并发扫描框架
│   └── save_results()            #   CSV/JSON 输出
│
├── run.py                        # 统一入口（编程式 scan()）
├── .gitignore
├── README.md
└── output/                       # 扫描结果输出
```

---

## 指标说明

| 脚本 | 函数 | 信号 | 多周期 |
|------|------|------|--------|
| `kline_pattern.py` | `match_pattern()` | 阴阳形态匹配 + 火地晋/水雷屯/地火明夷 | ✅ |
| `zhuli_xichou.py` | `zhuli_xichou()` | 🔴 主力进场 / 🟢 洗盘 | ✅ |
| `zhuli_chuhuo.py` | `zhuli_chuhuo()` | 🟢 主力出货 / 🔴 承接 | ✅ |
| `volume.py` | `check_volume_anomaly()` | 📈 倍量≥30% / 📉 缩量≥30% | ✅ |
| `volume.py` | `check_volume_breakout()` | 横盘放量突破（5步复合条件） | ✅ |

### 预设卦象（kline_pattern.py）

| 形态 | 卦名 |
|------|------|
| `101000` | 火地晋 |
| `010001` | 水雷屯 |
| `000101` | 地火明夷 |
| `010101` | 水火既济 |

### 量能异动标准（volume.py）

| 条件 | 判定 |
|------|------|
| 今日量 / 昨量 ≥ 1.30 | 📈 倍量 |
| 今日量 / 昨量 ≤ 0.70 | 📉 缩量 |
| 0.70 ~ 1.30 | 正常波动 |

---

## 多周期支持

所有指标脚本支持 `--period` 参数：

```bash
# 日线 / 周线 / 月线
python 指标/zhuli_xichou.py 600519 --period daily
python 指标/zhuli_xichou.py 600519 --period weekly
python 指标/zhuli_xichou.py 600519 --period monthly
```

编程时通过 `frequency` 参数控制：
- `frequency=4` — 日线
- `frequency=5` — 周线
- `frequency=6` — 月线

---

## 技术要点

- **数据源**：mootdx (通达信行情接口)
- **形态定义**：`close > open` 为阳(1)，否则为阴(0)
- **RSI算法**：Wilder平滑（非SMA）
- **股票代码格式**：`sh600519` / `sz000001`
- **mootdx frequency**：4=日线, 5=周线, 6=月线
- **mootdx 客户端**：`threading.local()` 线程安全，默认 20 并发

---

## 注意事项

- 下降趋势中主力吸筹可能连续出现进场信号，需结合趋势判断
- 上升趋势中主力出货可能连续出现出货信号，需结合趋势判断
- 一个月内连续同方向信号可能是趋势延续而非真实信号
- 建议结合 MA20/MA60 方向辅助判断

---

## 依赖

- Python 3.14+
- pandas, numpy
- mootdx (通达信行情接口)

---

---

## 每周关注 — GitHub Pages 展示

`docs/` 目录部署了每周关注股票列表的静态网页，通过 **GitHub Pages** 访问：

- **地址**: https://maoxianfei.github.io/fire-screener/
- **配置**: 仓库 Settings → Pages → 分支 `master`，目录 `/docs`
- **数据结构**: `docs/data/watchlists.json` (当前) + `docs/data/history/` (历史归档)
- **更新**: 修改 JSON 数据后推送即可自动生效（约1分钟）

具体数据格式和更新流程见 `docs/README.md`。

---

## 关联项目

- `~/claude_code/stock-strategy/` — 股票池管理、回测
- `~/claude_code/trading-advisor/` — 交易推荐系统（短线+ETF轮动）
