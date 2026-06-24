#!/usr/bin/env python3
"""
横盘放量突破 — 全市场A股筛选器
============================
策略逻辑:
1. 三倍量: 前一日成交量 >= 再前一日的3倍
2. 右侧多头: MA5>MA10>MA20>MA60 且 MA20上升
3. 缩量盘整: 三倍量之后每日成交量 < 三倍量当日成交量
4. 突破: 当前收盘价 > 三倍量当日收盘价 且 阳线
5. 盘整振幅: 三倍量之后的区间振幅 < 15%
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from base import get_stock_list, fetch_klines_list, scan_all, save_results


def check_breakout(code: str, name: str, max_range_ratio: float = 1.15) -> dict | None:
    """检查单只股票是否满足三倍量缩量盘整突破条件"""
    klines = fetch_klines_list(code, count=120)
    if len(klines) < 65:
        return None

    C = [k["close"] for k in klines]
    H = [k["high"] for k in klines]
    L = [k["low"] for k in klines]
    V = [k["volume"] for k in klines]
    O = [k["open"] for k in klines]
    dates = [k["date"] for k in klines]
    n = len(klines)

    # 寻找最近的三倍量日
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

    # 右侧多头: MA5>MA10>MA20>MA60 且 MA20上升
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

    # 缩量盘整
    for j in range(triple_idx + 1, n):
        if V[j] >= triple_vol:
            return None

    # 突破
    if not (C[n - 1] > triple_price and C[n - 1] > O[n - 1]):
        return None

    # 盘整振幅
    h_max = max(H[triple_idx + 1:n])
    l_min = min(L[triple_idx + 1:n])
    if l_min <= 0:
        return None
    range_ratio = h_max / l_min
    if range_ratio >= max_range_ratio:
        return None

    return {
        "code": code,
        "name": name,
        "triple_date": dates[triple_idx],
        "triple_price": triple_price,
        "triple_vol": triple_vol,
        "days_since": days_since,
        "current_close": C[n - 1],
        "current_date": dates[n - 1],
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
        "range_ratio": range_ratio,
        "breakout_pct": (C[n - 1] / triple_price - 1) * 100,
    }


def main():
    max_range = 1.15
    if len(sys.argv) > 1:
        try:
            max_range = float(sys.argv[1])
        except ValueError:
            pass

    print(f"{'=' * 60}")
    print(f"  横盘放量突破 — 全市场A股筛选")
    print(f"  盘整振幅上限: {(max_range - 1) * 100:.0f}%")
    print(f"{'=' * 60}")

    stock_list = get_stock_list()
    results, _ = scan_all(stock_list, lambda c, n: check_breakout(c, n, max_range),
                          workers=15, label="横盘放量突破")

    if results:
        results.sort(key=lambda x: x["breakout_pct"], reverse=True)
        print(f"\n{'代码':12s} {'名称':8s} {'现价':>8s} {'三倍量日':12s} {'三倍价':>8s} "
              f"{'天数':>4s} {'突破%':>7s} {'振幅':>6s} {'MA20':>8s}")
        print("-" * 85)
        for r in results:
            print(f"{r['code']:12s} {r['name']:8s} ¥{r['current_close']:>7.2f} "
                  f"{r['triple_date']:12s} ¥{r['triple_price']:>7.2f} "
                  f"{r['days_since']:>4d} {r['breakout_pct']:>+6.1f}% "
                  f"{r['range_ratio']:>5.2f} ¥{r['ma20']:>7.2f}")

        save_results(results, "横盘放量突破",
                     csv_columns=["股票代码", "股票名称", "最新收盘价", "三倍量日期", "三倍量收盘价",
                                  "盘整天数", "突破幅度%", "盘整振幅", "MA5", "MA10", "MA20", "MA60"],
                     csv_rows_fn=lambda r: [r["code"], r["name"], f"{r['current_close']:.2f}",
                                            r["triple_date"], f"{r['triple_price']:.2f}",
                                            r["days_since"], f"{r['breakout_pct']:.1f}",
                                            f"{r['range_ratio']:.3f}",
                                            f"{r['ma5']:.2f}", f"{r['ma10']:.2f}",
                                            f"{r['ma20']:.2f}", f"{r['ma60']:.2f}"])


if __name__ == "__main__":
    main()
