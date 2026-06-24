"""
K线形态筛选指标
===============
K线阴阳形态匹配与筛选工具，支持预设卦象形态。

╔═══════════════════════════════════════════════════════╗
║  ⚠️  基础脚本 — 禁止随意修改                        ║
╚═══════════════════════════════════════════════════════╝

形态定义：
- 1 = 阳线 (close > open)
- 0 = 阴线 (close <= open)

预设卦象：
    101000  火地晋   火在上、地在下，光明上升之象
    010001  水雷屯   水在上、雷在下，创始艰难之象
    000101  地火明夷 地在上、火在下，光明受伤之象

────────────────────────────────────────────────────
CLI 用法

  # 指定形态搜索（详细模式）
  python indicators/kline_pattern.py 101000 --code sz000970

  # 扫描全部预设卦象（摘要模式）
  python indicators/kline_pattern.py --code sz000970

  # 周线 / 月线
  python indicators/kline_pattern.py --code sz000970 --period weekly
  python indicators/kline_pattern.py --code sz000970 --period monthly

  # 自定义回看天数
  python indicators/kline_pattern.py --code sz000970 --lookback 20 --count 50

参数说明：
  pattern             形态二进制串（可选，省略则扫描全部卦象）
  --code              股票代码，如 sh600519 / sz000970
  --period / -p       周期: daily(日) weekly(周) monthly(月)
  --count             获取K线根数（默认60）
  --lookback          回看根数（默认30）

编程导入：
  from indicators.kline_pattern import (
      match_pattern,           # 单形态匹配
      multi_pattern_match,     # 多形态匹配
      pattern_to_string,       # K线→二进制字符串
      hexagram_name,           # 形态→卦象名称
      HEXAGRAM_MAP,            # 预设卦象字典
  )

  例:
      df = fetch_kline('sh600519', count=60)
      result = match_pattern(df, pattern="101000", lookback=30)
"""

import pandas as pd
import numpy as np
from typing import Optional

# ═══════════════════════════════════════════
# 预设卦象
# ═══════════════════════════════════════════

HEXAGRAM_MAP: dict[str, str] = {
    "101000": "火地晋",      # 火在上、地在下，光明上升
    "010001": "水雷屯",      # 水在上、雷在下，创始艰难
    "000101": "地火明夷",    # 地在上、火在下，光明受伤
}


def hexagram_name(pattern: str) -> str:
    """返回形态对应的卦象名称，未知形态返回 pattern 本身。"""
    return HEXAGRAM_MAP.get(pattern, pattern)


def pattern_to_string(df: pd.DataFrame, length: Optional[int] = None) -> str:
    """
    将K线的阴阳状态转换为二进制字符串。

    Parameters
    ----------
    df : DataFrame
        必须包含 'close' 和 'open' 列。
    length : int, optional
        取最近 N 根K线，默认全部。

    Returns
    -------
    str
        由 '1'（阳线）和 '0'（阴线）组成的字符串。
    """
    if length:
        df = df.tail(length)
    return "".join("1" if r['close'] > r['open'] else "0"
                   for _, r in df.iterrows())


def match_pattern(df: pd.DataFrame, pattern: str,
                  lookback: int = 30) -> Optional[dict]:
    """
    在最近 lookback 根K线中查找指定形态。

    Parameters
    ----------
    df : DataFrame
        日线K线数据，必须含 'close', 'open', 'date' 列。
    pattern : str
        目标形态二进制串，如 "101000"。
    lookback : int
        回看K线根数。

    Returns
    -------
    dict or None
        {
            "pattern": 目标形态,
            "position": 匹配起始位置(0-based),
            "match_start": 匹配起始日期,
            "match_end": 匹配结束日期,
            "daily_pattern": 完整二进制串,
            "last_close": 最新收盘价,
        }
        未匹配返回 None。
    """
    if df is None or len(df) < lookback:
        return None

    recent = df.tail(lookback)
    daily_pattern = pattern_to_string(recent)

    if pattern not in daily_pattern:
        return None

    idx = daily_pattern.find(pattern)
    matched = recent.iloc[idx:idx + len(pattern)]

    return {
        "pattern": pattern,
        "name": hexagram_name(pattern),
        "position": idx,
        "match_start": str(matched.iloc[0]['date']),
        "match_end": str(matched.iloc[-1]['date']),
        "daily_pattern": daily_pattern,
        "last_close": float(df.iloc[-1]['close']),
        "last_date": str(df.iloc[-1]['date']),
    }


def multi_pattern_match(df: pd.DataFrame, patterns: list[str],
                        lookback: int = 30) -> list[dict]:
    """
    多形态匹配——依次检查每个形态，返回所有命中结果。

    Parameters
    ----------
    df : DataFrame
    patterns : list[str]
        形态列表，如 ["101000", "100001", "111000"]。
    lookback : int

    Returns
    -------
    list[dict]
        每个命中返回一个 dict（同 match_pattern）。
    """
    results = []
    for pattern in patterns:
        result = match_pattern(df, pattern, lookback)
        if result:
            results.append(result)
    return results


def is_volume_breakout(df: pd.DataFrame, vol_window: int = 20,
                       multiplier: float = 1.5) -> bool:
    """
    判断最近一根K线是否放量突破（成交量 > 均量 × 倍数）。

    Parameters
    ----------
    df : DataFrame
        必须含 'volume' 列。
    vol_window : int
        均量计算周期。
    multiplier : float
        放量倍数阈值。

    Returns
    -------
    bool
    """
    if df is None or len(df) < vol_window + 1:
        return False
    recent_vol = df['volume'].tail(vol_window)
    avg_vol = recent_vol.mean()
    last_vol = float(df.iloc[-1]['volume'])
    return last_vol > avg_vol * multiplier


def last_candle_type(df: pd.DataFrame) -> str:
    """
    返回最新一根K线的类型: "阳线" | "阴线" | "十字星"

    十字星: abs(close - open) <= (high - low) * 0.1
    """
    if df is None or len(df) == 0:
        return "未知"
    last = df.iloc[-1]
    body = abs(float(last['close']) - float(last['open']))
    shadow = float(last['high']) - float(last['low'])
    if shadow == 0:
        return "阳线" if last['close'] >= last['open'] else "阴线"
    if body / shadow <= 0.1:
        return "十字星"
    return "阳线" if last['close'] > last['open'] else "阴线"


# ═══════════════════════════════════════════
# CLI 用法
# ═══════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    PERIOD_MAP = {"daily": 4, "weekly": 5, "monthly": 6}

    parser = argparse.ArgumentParser(description="K线形态筛选工具（支持预设卦象）")
    parser.add_argument("pattern", nargs="?", default=None,
                        help='目标形态二进制串，如 "101000"；省略则扫描所有预设卦象')
    parser.add_argument("--code", default="sh600519",
                        help="股票代码 (默认 sh600519)")
    parser.add_argument("--period", "-p", default="daily",
                        choices=list(PERIOD_MAP.keys()),
                        help="K线周期: daily=日线, weekly=周线, monthly=月线 (默认 daily)")
    parser.add_argument("--count", type=int, default=60,
                        help="获取K线根数 (默认 60)")
    parser.add_argument("--lookback", type=int, default=30,
                        help="回看根数 (默认 30)")
    args = parser.parse_args()

    # 获取数据
    from mootdx.quotes import Quotes
    client = Quotes.factory(market="std")
    raw = args.code.replace("sh", "").replace("sz", "")
    freq = PERIOD_MAP[args.period]
    df = client.bars(symbol=raw, frequency=freq, offset=args.count)
    if df is None or len(df) == 0:
        print(f"❌ 无法获取 {args.code} 的{args.period}线数据")
        exit(1)

    df = df.rename(columns={"datetime": "date", "vol": "volume"})
    df["date"] = df["date"].astype(str).str[:10]

    recent_pattern = pattern_to_string(df, args.lookback)

    print(f"{'=' * 64}")
    print(f"  {args.code}  {args.period}线  |  最近 {args.lookback} 根")
    print(f"  完整形态: {recent_pattern}")
    print(f"{'=' * 64}")
    print()

    # ── 模式1: 指定形态 ──
    if args.pattern:
        result = match_pattern(df, args.pattern, args.lookback)
        pname = hexagram_name(args.pattern)
        if result:
            print(f"✅ {args.pattern} {pname}  匹配成功")
            print(f"   位置: 第 {result['position']} 根")
            print(f"   区间: {result['match_start']} ~ {result['match_end']}")
            print(f"   收盘: ¥{result['last_close']:.2f}")
        else:
            print(f"❌ {args.pattern} {pname}  未匹配")

    # ── 模式2: 扫描全部预设卦象 ──
    else:
        results = multi_pattern_match(df, list(HEXAGRAM_MAP.keys()), args.lookback)
        hit = {r["pattern"] for r in results}

        print(f"{'卦象':<14} {'形态':>8} {'结果':>6}  {'区间'}")
        print(f"{'-' * 56}")
        for pat, gua in HEXAGRAM_MAP.items():
            status = "✅" if pat in hit else "❌"
            extra = ""
            if pat in hit:
                r = next(rr for rr in results if rr["pattern"] == pat)
                extra = f"  {r['match_start']} ~ {r['match_end']}"
            print(f"  {gua:<8} {pat:>8}  {status:>6}{extra}")
        print()
        print(f"  命中 {len(results)}/{len(HEXAGRAM_MAP)}  最新收盘: ¥{df.iloc[-1]['close']:.2f}")
