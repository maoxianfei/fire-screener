#!/usr/bin/env python3
"""
MA60上升趋势 — 全市场扫描
=========================
扫描全A股，筛选连续站上MA60的上升趋势股票。

用法:
    python 指标/scan_ma60.py                    # 全市场（默认20线程）
    python 指标/scan_ma60.py --market 688       # 仅科创板
    python 指标/scan_ma60.py --min-streak 10    # 至少连续10天
    python 指标/scan_ma60.py --workers 40       # 40线程并发
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse
from base import get_stock_list, scan_all, fetch_klines_list, save_results, print_table
from 指标.ma import check_ma60_uptrend


def check_ma60(code: str, name: str, min_streak: int = 5) -> dict | None:
    """单只股票MA60检查"""
    klines = fetch_klines_list(code, count=120)
    if not klines:
        return None
    result = check_ma60_uptrend(klines, min_streak=min_streak)
    if result is None:
        return None
    # 过滤：未达到最小连续天数
    if int(result["streak"]) < min_streak:
        return None
    return {
        "code": code,
        "name": name,
        "streak": int(result["streak"]),
        "close": float(round(result["close"], 2)),
        "ma60": float(result["ma60"]),
        "pct": float(result["pct"]),
        "passed_5d": bool(result["passed_5d"]),
        "passed_10d": bool(result["passed_10d"]),
        "passed_20d": bool(result["passed_20d"]),
    }


def main():
    parser = argparse.ArgumentParser(description="MA60上升趋势全市场扫描")
    parser.add_argument("--market", default="all", help="市场: all/sz/sh/688/30/60/00")
    parser.add_argument("--min-streak", type=int, default=5, help="最小连续天数 (默认5)")
    parser.add_argument("--workers", type=int, default=20, help="并发线程数 (默认20)")
    parser.add_argument("--save", action="store_true", help="保存结果到文件")
    args = parser.parse_args()

    stocks = get_stock_list(args.market)
    print(f"\n📋 MA60上升趋势扫描 | 市场={args.market} | 最小连续={args.min_streak}d | {len(stocks)}只\n")

    def check(code, name):
        return check_ma60(code, name, min_streak=args.min_streak)

    results, errors = scan_all(stocks, check, workers=args.workers,
                               label=f"MA60上升趋势 (≥{args.min_streak}d)")

    if not results:
        print("❌ 无命中")
        return

    # 按连续天数降序排列
    results.sort(key=lambda r: r["streak"], reverse=True)

    # 打印表格（使用简单文本格式避免格式化问题）
    print(f"\n{'代码':>10s} {'名称':>8s} {'天数':>4s} {'收盘':>8s} {'MA60':>8s} {'偏离%':>7s}")
    print("-" * 50)
    for r in results[:50]:
        print(f"{r['code']:>10s} {r['name']:>8s} {r['streak']:>4d} {r['close']:>8.2f} {r['ma60']:>8.2f} {r['pct']:>+7.1f}%")
    if len(results) > 50:
        print(f"... 共 {len(results)} 只，仅显示前50只")
    print(f"\n✅ 共命中 {len(results)} 只 (异常: {errors})")

    # 分段统计
    for days, label in [(20, "强势(≥20d)"), (10, "确认(≥10d)"), (5, "基础(≥5d)")]:
        count = sum(1 for r in results if r["streak"] >= days)
        print(f"  {label}: {count}只")

    # 保存
    if args.save:
        csv_columns = ["代码", "名称", "连续天数", "收盘", "MA60", "偏离%"]
        def csv_rows(r):
            return [r["code"], r["name"], r["streak"], r["close"], r["ma60"], f"{r['pct']:+.1f}%"]
        save_results(results, "MA60上升趋势", csv_columns=csv_columns, csv_rows_fn=csv_rows)


if __name__ == "__main__":
    main()
