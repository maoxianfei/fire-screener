"""
成交量指标
==========
成交量形态检测工具集：放量突破 + 量能异动（倍量/缩量）。

╔═══════════════════════════════════════════════════════╗
║  ⚠️  基础脚本 — 禁止随意修改                        ║
╚═══════════════════════════════════════════════════════╝

信号说明：
- check_volume_breakout: 横盘放量突破（5步复合条件）
- check_volume_anomaly:  量能异动检测（最新日 vs 前日，±30%为标准阈值）

支持多周期：日线 / 周线 / 月线（传入对应周期的K线数据即可）。

────────────────────────────────────────────────────
CLI 用法

  # 放量突破检测
  python 指标/volume.py breakout --code sz000970

  # 量能异动检测（默认±30%）
  python 指标/volume.py anomaly --code sz000970

  # 自定义异动阈值
  python 指标/volume.py anomaly --code sz000970 --up 1.5 --down 0.5

  # 周线
  python 指标/volume.py breakout --code sz000970 --period weekly

参数说明：
  command             breakout(放量突破) 或 anomaly(量能异动)
  --code              股票代码
  --period / -p       daily(日) weekly(周) monthly(月)
  --count             获取K线根数（默认120）
  --up                放量阈值（仅anomaly，默认1.30=上涨30%）
  --down              缩量阈值（仅anomaly，默认0.70=下跌30%）

编程导入：
  from 指标.volume import check_volume_breakout, check_volume_anomaly

  例:
      from base import fetch_klines_list
      klines = fetch_klines_list('sz000970', count=120)
      result = check_volume_breakout(klines)
      if result:
          print(f"放量突破: {result['breakout_pct']:.1f}%")

      result = check_volume_anomaly(klines)
      if result:
          print(f"量能异动: {result['anomaly_type']}  量比={result['vol_ratio']:.2f}")

输出列说明:
  check_volume_breakout:
    triple_date      三倍量日期
    triple_price     三倍量收盘价
    triple_vol       三倍量成交量
    days_since       盘整天数
    current_close    最新收盘价
    range_ratio      盘整振幅
    breakout_pct     突破幅度%
    ma5/ma10/ma20/ma60  均线

  check_volume_anomaly:
    anomaly_type     异动类型: "倍量" / "缩量"
    date             日期
    close            收盘价
    change_pct       涨跌幅%
    today_vol        今日成交量
    yest_vol         昨日成交量
    vol_ratio        量比
"""

import sys
import os
from typing import Optional


# ═══════════════════════════════════════════
# 放量突破检测（5步复合条件）
# ═══════════════════════════════════════════

def check_volume_breakout(klines: list[dict],
                          max_range_ratio: float = 1.15) -> Optional[dict]:
    """
    横盘放量突破检测。

    5步条件：
    1. 三倍量 — 前一日成交量 ≥ 再前一日的3倍
    2. 右侧多头 — MA5>MA10>MA20>MA60 且 MA20上升
    3. 缩量盘整 — 三倍量之后每日成交量 < 三倍量当日量
    4. 突破 — 当前收盘价 > 三倍量收盘价 且 为阳线
    5. 振幅限制 — 盘整区间最高/最低 < max_range_ratio

    Parameters
    ----------
    klines : list[dict]
        K线数据，每项含 date, open, close, high, low, volume。
    max_range_ratio : float
        盘整振幅上限（默认1.15=15%）。

    Returns
    -------
    dict or None
        命中返回信号字典，未命中返回 None。
    """
    if len(klines) < 65:
        return None

    C = [k["close"] for k in klines]
    H = [k["high"] for k in klines]
    L = [k["low"] for k in klines]
    V = [k["volume"] for k in klines]
    O = [k["open"] for k in klines]
    dates = [k["date"] for k in klines]
    n = len(klines)

    # ① 寻找最近的三倍量日
    triple_idx = -1
    for i in range(n - 1, 1, -1):
        if V[i - 1] >= V[i - 2] * 3:
            triple_idx = i - 1
            break
    if triple_idx < 0:
        return None

    days_since = n - 1 - triple_idx
    if days_since < 3 or days_since > 60:
        return None

    triple_price = C[triple_idx]
    triple_vol = V[triple_idx]

    # ② 右侧多头: MA5>MA10>MA20>MA60 且 MA20上升
    i = n - 1
    if i < 59:
        return None
    ma5 = sum(C[i - 4:i + 1]) / 5
    ma10 = sum(C[i - 9:i + 1]) / 10
    ma20 = sum(C[i - 19:i + 1]) / 20
    ma60 = sum(C[i - 59:i + 1]) / 60
    ma20_prev = sum(C[i - 20:i]) / 20

    if not (ma5 > ma10 > ma20 > ma60):
        return None
    if ma20 <= ma20_prev:
        return None

    # ③ 缩量盘整
    for j in range(triple_idx + 1, n):
        if V[j] >= triple_vol:
            return None

    # ④ 突破
    if not (C[n - 1] > triple_price and C[n - 1] > O[n - 1]):
        return None

    # ⑤ 盘整振幅限制
    h_max = max(H[triple_idx + 1:n])
    l_min = min(L[triple_idx + 1:n])
    if l_min <= 0:
        return None
    range_ratio = h_max / l_min
    if range_ratio >= max_range_ratio:
        return None

    return {
        "triple_date": dates[triple_idx],
        "triple_price": triple_price,
        "triple_vol": triple_vol,
        "days_since": days_since,
        "current_close": C[n - 1],
        "current_date": dates[n - 1],
        "ma5": round(ma5, 2),
        "ma10": round(ma10, 2),
        "ma20": round(ma20, 2),
        "ma60": round(ma60, 2),
        "range_ratio": round(range_ratio, 3),
        "breakout_pct": round((C[n - 1] / triple_price - 1) * 100, 1),
    }


# ═══════════════════════════════════════════
# 量能异动检测（倍量 / 缩量）
# ═══════════════════════════════════════════

def check_volume_anomaly(klines: list[dict],
                         up_threshold: float = 1.30,
                         down_threshold: float = 0.70) -> Optional[dict]:
    """
    量能异动检测——最新交易日成交量对比前一日，判断是否异常放量或缩量。

    标准阈值：上涨≥30%（倍量）或 下跌≥30%（缩量）视为异动。

    Parameters
    ----------
    klines : list[dict]
        K线数据，每项含 date, open, close, high, low, volume。
    up_threshold : float
        放量阈值（默认1.30=量比≥1.30视为倍量）。
    down_threshold : float
        缩量阈值（默认0.70=量比≤0.70视为缩量）。

    Returns
    -------
    dict or None
        命中返回：
            anomaly_type    "倍量" 或 "缩量"
            date            日期
            close           收盘价
            change_pct      涨跌幅%
            today_vol       今日成交量
            yest_vol        昨日成交量
            vol_ratio       量比
        无异常返回 None。
    """
    if len(klines) < 3:
        return None

    today = klines[-1]
    yesterday = klines[-2]

    today_vol = float(today.get("volume", 0))
    yest_vol = float(yesterday.get("volume", 0))

    if yest_vol <= 0:
        return None

    ratio = today_vol / yest_vol

    if ratio >= up_threshold:
        anomaly_type = "倍量"
    elif ratio <= down_threshold:
        anomaly_type = "缩量"
    else:
        return None  # 无异常

    today_close = float(today.get("close", 0))
    today_change = (today_close / float(yesterday.get("close", 1)) - 1) * 100

    return {
        "anomaly_type": anomaly_type,
        "date": str(today.get("date", "")),
        "close": today_close,
        "change_pct": round(today_change, 1),
        "today_vol": today_vol,
        "yest_vol": yest_vol,
        "vol_ratio": round(ratio, 2),
    }


# ═══════════════════════════════════════════
# CLI 用法
# ═══════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    PERIOD_MAP = {"daily": 4, "weekly": 5, "monthly": 6}

    parser = argparse.ArgumentParser(description="成交量指标工具")
    parser.add_argument("command", choices=["breakout", "anomaly"],
                        help="breakout=放量突破, anomaly=量能异动")
    parser.add_argument("--code", default="sh600519",
                        help="股票代码 (默认 sh600519)")
    parser.add_argument("--period", "-p", default="daily",
                        choices=list(PERIOD_MAP.keys()),
                        help="K线周期 (默认 daily)")
    parser.add_argument("--count", type=int, default=120,
                        help="获取K线根数 (默认 120)")
    parser.add_argument("--up", type=float, default=1.30,
                        help="放量阈值，仅anomaly (默认1.30=上涨30%%)")
    parser.add_argument("--down", type=float, default=0.70,
                        help="缩量阈值，仅anomaly (默认0.70=下跌30%%)")
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

    # 标准化列名并转为 list[dict]
    df = df.rename(columns={"datetime": "date", "vol": "volume"})
    df["date"] = df["date"].astype(str).str[:10]
    klines = df.to_dict("records")

    if args.command == "breakout":
        result = check_volume_breakout(klines)
        if result:
            print(f"\n✅ 横盘放量突破 — 命中")
            print(f"   三倍量日: {result['triple_date']}  ¥{result['triple_price']:.2f}")
            print(f"   盘整 {result['days_since']} 天  振幅 {result['range_ratio']:.1%}")
            print(f"   突破幅度: {result['breakout_pct']:+.1f}%")
            print(f"   最新收盘: ¥{result['current_close']:.2f}")
            print(f"   MA5={result['ma5']:.2f}  MA10={result['ma10']:.2f}")
            print(f"   MA20={result['ma20']:.2f}  MA60={result['ma60']:.2f}")
        else:
            print(f"\n❌ 横盘放量突破 — 未命中")

    elif args.command == "anomaly":
        result = check_volume_anomaly(klines, args.up, args.down)
        if result:
            icon = "📈" if result["anomaly_type"] == "倍量" else "📉"
            print(f"\n{icon} 量能异动 — {result['anomaly_type']}")
            print(f"   日期: {result['date']}  收盘: ¥{result['close']:.2f}")
            print(f"   涨跌: {result['change_pct']:+.1f}%")
            print(f"   量比: {result['vol_ratio']:.2f} ({result['anomaly_type']})")
            print(f"   今量: {result['today_vol']:.0f}  昨量: {result['yest_vol']:.0f}")
        else:
            print(f"\n➖ 量能正常 — 无异动")
