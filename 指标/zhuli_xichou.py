"""
主力吸筹指标
============
从通达信公式转换而来的主力吸筹识别指标。

╔═══════════════════════════════════════════════════════╗
║  ⚠️  基础脚本 — 禁止随意修改                        ║
╚═══════════════════════════════════════════════════════╝

信号说明：
- 主力进场（红色）: VAR5 上升，表示主力在吸筹
- 洗盘（绿色）: VAR5 下降，表示主力在洗盘

注意事项（局限性）：
- 下降趋势中价格反复创新低，LOW<=LLV(LOW,33) 条件频繁触发，
  可能导致连续出现主力进场信号（VAR5持续上升）。
- 若一个月内连续出现进场信号，需结合趋势判断：
  真正的吸筹通常出现在下跌末端、信号由弱转强；
  连续信号伴随持续下跌，可能是趋势延续而非主力吸筹。
- 建议结合其他趋势指标（如MA20/MA60方向）辅助判断。

支持多周期：日线 / 周线 / 月线。

────────────────────────────────────────────────────
CLI 用法

  # 日线扫描（默认）
  python 指标/zhuli_xichou.py 000970

  # 周线 / 月线
  python 指标/zhuli_xichou.py 000970 --period weekly
  python 指标/zhuli_xichou.py 000970 --period monthly

  # 自定义数据量
  python 指标/zhuli_xichou.py 600519 --count 200

参数说明：
  code                股票代码（可选，默认600519）
  --period / -p       daily(日) weekly(周) monthly(月)
  --count / -c        获取K线根数（默认150）

编程导入：
  from 指标.zhuli_xichou import zhuli_xichou, fetch_kline, sma

  例:
      df = fetch_kline('sh600519', count=150, frequency=4)  # 日线
      df = zhuli_xichou(df)
      signals = df[df['zlxc_jinchang'] > 0]   # 筛选进场信号

输出列说明:
  zlxc_var5           核心指标值
  zlxc_jinchang       主力进场（正值=进场信号）
  zlxc_xipan          洗盘（正值=洗盘信号）
"""

import pandas as pd
import numpy as np

# mootdx frequency 参数映射
PERIOD_MAP = {
    "daily":   4,    # 日线
    "weekly":  5,    # 周线
    "monthly": 6,    # 月线
}
PERIOD_NAMES = {v: k for k, v in PERIOD_MAP.items()}


def sma(series: pd.Series, n: int, m: int) -> pd.Series:
    """
    通达信 SMA(X, N, M) = (M * X + (N - M) * REF(SMA, 1)) / N
    递推加权移动平均，跳过 NaN 起始值。
    """
    result = pd.Series(np.nan, index=series.index)
    first_valid = series.first_valid_index()
    if first_valid is None:
        return result
    start = series.index.get_loc(first_valid)
    result.iloc[start] = series.iloc[start]
    for i in range(start + 1, len(series)):
        if np.isnan(series.iloc[i]):
            result.iloc[i] = result.iloc[i - 1]
        else:
            result.iloc[i] = (m * series.iloc[i] + (n - m) * result.iloc[i - 1]) / n
    return result


def zhuli_xichou(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算主力吸筹指标。

    Parameters
    ----------
    df : DataFrame
        必须包含小写列: open, high, low, close

    Returns
    -------
    DataFrame
        新增列:
        - zlxc_var5:     核心指标值
        - zlxc_jinchang: 主力进场 (正值=进场信号)
        - zlxc_xipan:    洗盘 (正值=洗盘信号)
    """
    low = df['low']
    open_ = df['open']
    close = df['close']
    high = df['high']

    avg_price = (low + open_ + close + high) / 4
    var1 = avg_price.shift(1)
    diff = low - var1

    numerator = sma(diff.abs(), 13, 1)
    denominator = sma(diff.clip(lower=0), 10, 1)
    var2 = numerator / denominator.replace(0, np.nan)

    var3 = var2.ewm(span=10, adjust=False).mean()
    var4 = low.rolling(window=33, min_periods=1).min()
    conditional = pd.Series(np.where(low <= var4, var3, 0), index=df.index)
    var5 = conditional.ewm(span=3, adjust=False).mean()

    var5_prev = var5.shift(1)
    jinchang = pd.Series(np.where(var5 > var5_prev, var5, 0), index=df.index)
    xipan = pd.Series(np.where(var5 < var5_prev, var5, 0), index=df.index)

    df = df.copy()
    df['zlxc_var5'] = var5
    df['zlxc_jinchang'] = jinchang
    df['zlxc_xipan'] = xipan
    return df


def fetch_kline(code: str, count: int = 120, frequency: int = 4) -> pd.DataFrame:
    """
    从 mootdx 获取K线数据。

    Parameters
    ----------
    code : str
        'sh600519' 或 'sz000001' 或 '600519' 格式。
    count : int
        获取K线根数。
    frequency : int
        周期: 4=日线, 5=周线, 6=月线 (默认 4 日线)。

    Returns
    -------
    DataFrame
    """
    from mootdx.quotes import Quotes

    raw = code.replace('sh', '').replace('sz', '')
    client = Quotes.factory(market='std')
    df = client.bars(symbol=raw, frequency=frequency, offset=count)

    if df is None or len(df) == 0:
        raise ValueError(f"无法获取 {code} 的K线数据（frequency={frequency}）")

    df = df.rename(columns={'datetime': 'date', 'vol': 'volume'})
    for col in ['open', 'close', 'high', 'low']:
        df[col] = df[col].astype(float)
    df['date'] = df['date'].astype(str).str[:10]
    return df


# ═══════════════════════════════════════════
# CLI 用法
# ═══════════════════════════════════════════

if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="主力吸筹指标")
    parser.add_argument("code", nargs="?", default="600519",
                        help="股票代码 (默认 600519)")
    parser.add_argument("--period", "-p", default="daily",
                        choices=list(PERIOD_MAP.keys()),
                        help="K线周期: daily=日线, weekly=周线, monthly=月线 (默认 daily)")
    parser.add_argument("--count", "-c", type=int, default=150,
                        help="获取K线根数 (默认 150)")
    args = parser.parse_args()

    freq = PERIOD_MAP[args.period]
    print(f"正在获取 {args.code} {args.period}线数据 (frequency={freq})...")
    df = fetch_kline(args.code, count=args.count, frequency=freq)
    df = zhuli_xichou(df)

    cols = ['date', 'open', 'close', 'low', 'high', 'zlxc_var5', 'zlxc_jinchang', 'zlxc_xipan']
    print(f"\n{'=' * 80}")
    print(f"  主力吸筹指标 — {args.code} ({args.period}线)")
    print(f"{'=' * 80}")
    print(f"{'日期':>12}  {'收盘':>8}  {'VAR5':>10}  {'信号'}")
    print(f"{'-' * 50}")
    for _, row in df[cols].tail(20).iterrows():
        if row['zlxc_jinchang'] > 0:
            signal = '🔴 主力进场'
        elif row['zlxc_xipan'] > 0:
            signal = '🟢 洗盘'
        else:
            signal = '   ─'
        print(f"{row['date']:>12}  {row['close']:>8.2f}  "
              f"{row['zlxc_var5']:>10.4f}  {signal}")
