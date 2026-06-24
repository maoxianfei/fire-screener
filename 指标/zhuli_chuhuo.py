"""
主力出货指标
============
与主力吸筹指标对称，检测高位出货信号。

╔═══════════════════════════════════════════════════════╗
║  ⚠️  基础脚本 — 禁止随意修改                        ║
╚═══════════════════════════════════════════════════════╝

信号说明：
- 主力出货（绿色）: VAR5 上升，高点创新高时出货
- 洗盘（红色）: VAR5 下降，出货力度减弱

注意事项（局限性）：
- 上升趋势中价格反复创新高，HIGH>=HHV(HIGH,33) 条件频繁触发，
  可能导致连续出现主力出货信号（VAR5持续上升）。
- 若一个月内连续出现出货信号，需结合趋势判断：
  真正的出货通常出现在上涨末端、高位放量滞涨；
  连续信号伴随持续上涨，可能是趋势延续而非主力出货。
- 建议结合其他趋势指标（如MA20/MA60方向、成交量）辅助判断。

支持多周期：日线 / 周线 / 月线。

与主力吸筹的对称关系：
- 吸筹看 LOW <= LLV(LOW, 33)  → 低位创新低时吸筹
- 出货看 HIGH >= HHV(HIGH, 33) → 高位创新高时出货

────────────────────────────────────────────────────
CLI 用法

  # 日线扫描（默认）
  python 指标/zhuli_chuhuo.py 000970

  # 周线 / 月线
  python 指标/zhuli_chuhuo.py 000970 --period weekly
  python 指标/zhuli_chuhuo.py 000970 --period monthly

  # 自定义数据量
  python 指标/zhuli_chuhuo.py 600519 --count 200

参数说明：
  code                股票代码（可选，默认600519）
  --period / -p       daily(日) weekly(周) monthly(月)
  --count / -c        获取K线根数（默认150）

编程导入：
  from 指标.zhuli_chuhuo import zhuli_chuhuo

  例:
      df = fetch_kline('sh600519', count=150, frequency=4)  # 日线
      df = zhuli_chuhuo(df)
      signals = df[df['zlch_chuhuo'] > 0]   # 筛选出货信号

输出列说明:
  zlch_var5           核心指标值
  zlch_chuhuo         主力出货（正值=出货信号）
  zlch_chengjie       洗盘（正值=洗盘信号）

依赖：
  指标.zhuli_xichou.sma  — 复用 SMA 递推算法
  指标.zhuli_xichou.fetch_kline — 复用数据获取
  指标.zhuli_xichou.PERIOD_MAP  — 复用周期映射
"""

import pandas as pd
import numpy as np

# 兼容包导入和直接脚本运行
try:
    from 指标.zhuli_xichou import sma
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from 指标.zhuli_xichou import sma


def zhuli_chuhuo(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算主力出货指标。

    Parameters
    ----------
    df : DataFrame
        必须包含小写列: open, high, low, close

    Returns
    -------
    DataFrame
        新增列:
        - zlch_var5:     核心指标值
        - zlch_chuhuo:   主力出货 (正值=出货信号)
        - zlch_chengjie: 承接 (正值=承接信号)
    """
    low = df['low']
    open_ = df['open']
    close = df['close']
    high = df['high']

    avg_price = (low + open_ + close + high) / 4
    var1 = avg_price.shift(1)

    # 对称：吸筹用 LOW-VAR1，出货用 HIGH-VAR1
    diff = high - var1
    numerator = sma(diff.abs(), 13, 1)
    denominator = sma(diff.clip(lower=0), 10, 1)
    var2 = numerator / denominator.replace(0, np.nan)

    var3 = var2.ewm(span=10, adjust=False).mean()

    # 对称：吸筹用 LLV(LOW,33)，出货用 HHV(HIGH,33)
    var4 = high.rolling(window=33, min_periods=1).max()
    conditional = pd.Series(np.where(high >= var4, var3, 0), index=df.index)
    var5 = conditional.ewm(span=3, adjust=False).mean()

    var5_prev = var5.shift(1)
    chuhuo = pd.Series(np.where(var5 > var5_prev, var5, 0), index=df.index)
    chengjie = pd.Series(np.where(var5 < var5_prev, var5, 0), index=df.index)

    df = df.copy()
    df['zlch_var5'] = var5
    df['zlch_chuhuo'] = chuhuo
    df['zlch_chengjie'] = chengjie
    return df


# ═══════════════════════════════════════════
# CLI 用法
# ═══════════════════════════════════════════

if __name__ == '__main__':
    import sys
    import argparse
    try:
        from 指标.zhuli_xichou import fetch_kline, PERIOD_MAP
    except ImportError:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from 指标.zhuli_xichou import fetch_kline, PERIOD_MAP

    parser = argparse.ArgumentParser(description="主力出货指标")
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
    df = zhuli_chuhuo(df)

    cols = ['date', 'open', 'close', 'low', 'high', 'zlch_var5', 'zlch_chuhuo', 'zlch_chengjie']
    print(f"\n{'=' * 80}")
    print(f"  主力出货指标 — {args.code} ({args.period}线)")
    print(f"{'=' * 80}")
    print(f"{'日期':>12}  {'收盘':>8}  {'VAR5':>10}  {'信号'}")
    print(f"{'-' * 50}")
    for _, row in df[cols].tail(20).iterrows():
        if row['zlch_chuhuo'] > 0:
            signal = '🟢 主力出货'
        elif row['zlch_chengjie'] > 0:
            signal = '🔴 洗盘'
        else:
            signal = '   ─'
        print(f"{row['date']:>12}  {row['close']:>8.2f}  "
              f"{row['zlch_var5']:>10.4f}  {signal}")
