#!/usr/bin/env python3
"""
周线形态筛选器
=============
策略: 在最近N周内寻找指定的周线阴阳形态
定义: 1=阳线(close>open), 0=阴线(close<=open)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from base import get_stock_list, fetch_klines, scan_all, save_results, daily_to_weekly


def check_weekly_pattern(code: str, name: str, pattern: str = "101000",
                         lookback: int = 10) -> dict | None:
    """检查单只股票是否匹配周线形态"""
    klines_raw = fetch_klines(code, count=120)
    if klines_raw is None or len(klines_raw) < 20:
        return None

    klines = klines_raw.to_dict('records')
    weekly = daily_to_weekly(klines)
    if len(weekly) < len(pattern):
        return None

    recent = weekly[-lookback:]
    if len(recent) < len(pattern):
        return None

    yy = "".join("1" if w["close"] > w["open"] else "0" for w in recent)

    if pattern not in yy:
        return None

    idx = yy.find(pattern)
    matched = recent[idx:idx + len(pattern)]

    return {
        "code": code,
        "name": name,
        "match_start": matched[0]["date"],
        "match_end": matched[-1]["date"],
        "weekly_pattern": yy,
        "match_pos": idx,
        "last_close": recent[-1]["close"],
        "last_date": recent[-1]["date"],
    }


def main():
    pattern = "101000"
    lookback = 10
    if len(sys.argv) > 1:
        pattern = sys.argv[1]
    if len(sys.argv) > 2:
        lookback = int(sys.argv[2])

    print(f"{'=' * 60}")
    print(f"  周线形态筛选")
    print(f"  目标形态: {pattern}")
    print(f"  回看周数: {lookback}")
    print(f"{'=' * 60}")

    stock_list = get_stock_list()
    results, _ = scan_all(stock_list, lambda c, n: check_weekly_pattern(c, n, pattern, lookback),
                          workers=15, label=f"周线形态 {pattern}")

    if results:
        results.sort(key=lambda x: x["name"])
        print(f"\n{'代码':12s} {'名称':8s} {'收盘':>8s} {'匹配区间':>25s} {'周线形态'}")
        print("-" * 85)
        for r in results:
            print(f"{r['code']:12s} {r['name']:8s} ¥{r['last_close']:>7.2f} "
                  f"{r['match_start']}~{r['match_end']} {r['weekly_pattern']}")

        save_results(results, f"周线形态{pattern}",
                     csv_columns=["股票代码", "股票名称", "最新收盘价", "匹配开始", "匹配结束", "匹配位置", "周线形态"],
                     csv_rows_fn=lambda r: [r["code"], r["name"], f"{r['last_close']:.2f}",
                                            r["match_start"], r["match_end"], r["match_pos"], r["weekly_pattern"]])


if __name__ == "__main__":
    main()
