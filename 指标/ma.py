"""
均线指标
========
价格与均线位置关系检测 + MA60上升趋势判定。

╔═══════════════════════════════════════════════════════╗
║  ⚠️  基础脚本 — 禁止随意修改                        ║
╚═══════════════════════════════════════════════════════╝

信号说明：
- check_ma_position:  检测最新收盘价在各周期均线上的位置
- check_ma60_uptrend: 检测日K是否连续在MA60上方运行（上升趋势判定）

MA60上升趋势判定：
  从最新日向前统计收盘价连续站上MA60的天数，
  判断是否满足 5天/10天/20天 的连续运行标准。

────────────────────────────────────────────────────
CLI 用法

  # 查看 MA10/MA20/MA60 位置
  python 指标/ma.py position --code sz000970

  # 检测 MA60 上升趋势
  python 指标/ma.py uptrend --code sz000970

参数说明：
  --code              股票代码
  --period / -p       daily(日) weekly(周) monthly(月)
  --count             获取K线根数（默认120）

编程导入：
  from 指标.ma import check_ma_position, check_ma60_uptrend

  例:
      from base import fetch_klines_list
      klines = fetch_klines_list('sz000970', count=120)
      result = check_ma60_uptrend(klines)
      print(f"连续 {result['streak']} 天在MA60上方")

输出列说明:
  --- check_ma_position ---
  close              最新收盘价
  ma_{n}             各周期均线值
  above_{n}          是否在均线上方

  --- check_ma60_uptrend ---
  streak             连续在MA60上方天数
  passed_5d          是否连续5天（基础上升）
  passed_10d         是否连续10天（趋势确认）
  passed_20d         是否连续20天（强势趋势）
  ma60               当前MA60值
"""

import sys
from typing import Optional


def check_ma_position(klines: list[dict],
                      mas: list[int] = None) -> Optional[dict]:
    """
    检测最新收盘价在各周期均线上的位置。

    Parameters
    ----------
    klines : list[dict]
        K线数据，每项含 close, date。
    mas : list[int]
        均线周期列表，默认 [10, 20, 60]。

    Returns
    -------
    dict or None
        数据不足时返回 None。
    """
    if mas is None:
        mas = [10, 20, 60]

    if len(klines) < max(mas):
        return None

    closes = [k["close"] for k in klines]
    n = len(closes)
    last_close = closes[-1]
    last_date = str(klines[-1]["date"])

    result = {
        "close": last_close,
        "date": last_date,
    }

    above_count = 0
    for period in mas:
        ma = sum(closes[n - period:]) / period
        above = last_close > ma
        pct = (last_close / ma - 1) * 100
        result[f"ma_{period}"] = round(ma, 2)
        result[f"above_{period}"] = above
        result[f"pct_{period}"] = round(pct, 1)
        if above:
            above_count += 1

    result["above_all"] = above_count == len(mas)
    result["above_count"] = above_count
    result["mas"] = mas
    return result


# ═══════════════════════════════════════════
# MA60 上升趋势判定
# ═══════════════════════════════════════════

def _calc_ma60(closes: list[float], i: int) -> float:
    """计算第 i 个位置的 MA60（向前取60根）"""
    return sum(closes[i - 59:i + 1]) / 60


def check_ma60_uptrend(klines: list[dict],
                       min_streak: int = 5) -> Optional[dict]:
    """
    检测日K是否连续在MA60上方运行（上升趋势判定）。

    从最新交易日向前统计，计算收盘价连续站上MA60的天数。
    判断是否满足 5天（基础）、10天（确认）、20天（强势）。

    Parameters
    ----------
    klines : list[dict]
        K线数据，需含 close, date。
    min_streak : int
        最小连续天数（默认5）。

    Returns
    -------
    dict or None
        数据不足(需至少80根)返回 None。
    """
    if len(klines) < 80:
        return None

    closes = [k["close"] for k in klines]
    n = len(closes)

    # 从最新日向前统计连续在MA60上方的天数
    streak = 0
    for i in range(n - 1, 59, -1):
        ma60 = _calc_ma60(closes, i)
        if closes[i] > ma60:
            streak += 1
        else:
            break

    last_date = str(klines[-1]["date"])
    last_close = closes[-1]
    current_ma60 = _calc_ma60(closes, n - 1)

    return {
        "streak": streak,
        "passed_5d": streak >= 5,
        "passed_10d": streak >= 10,
        "passed_20d": streak >= 20,
        "close": last_close,
        "date": last_date,
        "ma60": round(current_ma60, 2),
        "pct": round((last_close / current_ma60 - 1) * 100, 1),
    }


# ═══════════════════════════════════════════
# CLI 用法
# ═══════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    PERIOD_MAP = {"daily": 4, "weekly": 5, "monthly": 6}

    parser = argparse.ArgumentParser(description="均线指标工具")
    parser.add_argument("command", choices=["position", "uptrend"],
                        help="position=均线位置, uptrend=MA60上升趋势")
    parser.add_argument("--code", default="sh600519",
                        help="股票代码 (默认 sh600519)")
    parser.add_argument("--period", "-p", default="daily",
                        choices=list(PERIOD_MAP.keys()),
                        help="K线周期 (默认 daily)")
    parser.add_argument("--count", type=int, default=120,
                        help="获取K线根数 (默认 120)")
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
    klines = df.to_dict("records")

    if args.command == "position":
        mas = [10, 20, 60]
        result = check_ma_position(klines, mas)
        if result is None:
            print(f"❌ 数据不足")
            exit(1)

        print(f"\n  {args.code}  {args.period}线")
        print(f"  日期: {result['date']}  收盘: ¥{result['close']:.2f}")
        print(f"{'-' * 40}")
        for period in mas:
            icon = "📈" if result[f"above_{period}"] else "📉"
            print(f"  MA{period:<2}: ¥{result[f'ma_{period}']:.2f}  "
                  f"{icon} {result[f'pct_{period}']:+.1f}%")
        total = len(mas)
        print(f"{'-' * 40}")
        if result["above_all"]:
            print(f"  ✅ 价格在所有均线之上 ({result['above_count']}/{total})")
        else:
            print(f"  ⚠️  {result['above_count']}/{total} 条均线上方")

    elif args.command == "uptrend":
        result = check_ma60_uptrend(klines)
        if result is None:
            print(f"❌ 数据不足，需要至少80根K线")
            exit(1)

        print(f"\n  {args.code}  MA60上升趋势检测")
        print(f"{'=' * 40}")
        print(f"  日期: {result['date']}")
        print(f"  收盘: ¥{result['close']:.2f}")
        print(f"  MA60: ¥{result['ma60']:.2f}  ({result['pct']:+.1f}%)")
        print(f"{'=' * 40}")
        print(f"  连续在MA60上方: {result['streak']} 天")
        print(f"{'=' * 40}")
        checks = [
            (5, "基础上升"), (10, "趋势确认"), (20, "强势趋势"),
        ]
        for days, label in checks:
            key = f"passed_{days}d"
            icon = "✅" if result[key] else "❌"
            print(f"  {icon} 连续 {days:>2}d  {label}")

