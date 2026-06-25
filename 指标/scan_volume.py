#!/usr/bin/env python3
"""
成交量形态扫描 — 缩量后放量突破 MA120
=====================================
寻找类似"浙江龙盛"形态：
  1. 成交量长期在 MA120 下方运行（缩量期）
  2. 最近成交量放量突破 MA120（放量突破）
  3. 伴随价格上涨（可选）

用法:
    python 指标/scan_volume.py                          # 全市场
    python 指标/scan_volume.py --market 688             # 仅科创板
    python 指标/scan_volume.py --min-below 15           # 至少缩量15天
    python 指标/scan_volume.py --volume-ratio 1.3       # 放量阈值 1.3倍
    python 指标/scan_volume.py --save                   # 保存CSV/JSON
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse
from base import get_stock_list, scan_all, fetch_klines_list, save_results


def check_volume_pattern(code: str, name: str,
                         min_below_days: int = 10,
                         volume_ratio: float = 1.2,
                         check_days: int = 5) -> dict | None:
    """
    检测"缩量后放量突破MA120"形态

    Parameters
    ----------
    code : str
        股票代码
    name : str
        股票名称
    min_below_days : int
        缩量期最小连续天数 (默认10天)
    volume_ratio : float
        放量阈值，量/MA120 >= 此值视为放量 (默认1.2)
    check_days : int
        检查最近几天内是否有放量突破 (默认5天)

    Returns
    -------
    dict or None
        匹配返回形态信息，不匹配返回 None
    """
    klines = fetch_klines_list(code, count=200)
    if not klines or len(klines) < 130:
        return None

    volumes = [k['volume'] for k in klines]
    closes = [k['close'] for k in klines]
    n = len(volumes)

    # ── 计算 MA120 均量 ──
    ma120_vol = []
    for i in range(n):
        if i < 119:
            ma120_vol.append(None)
        else:
            ma120_vol.append(sum(volumes[i - 119:i + 1]) / 120)

    # ── 从后向前扫描 ──
    # 阶段1: 检查最近 check_days 天内是否有放量突破
    break_idx = -1
    for i in range(n - 1, n - check_days - 1, -1):
        if ma120_vol[i] and volumes[i] >= ma120_vol[i] * volume_ratio:
            break_idx = i
            break

    if break_idx == -1:
        return None  # 最近无放量突破

    # 阶段2: 从 break_idx 向前统计连续缩量天数
    below_streak = 0
    for i in range(break_idx - 1, 119, -1):
        if ma120_vol[i] and volumes[i] < ma120_vol[i]:
            below_streak += 1
        else:
            break

    if below_streak < min_below_days:
        return None  # 缩量期不够长

    # 阶段3: 统计缩量期中最低量比
    min_ratio = float('inf')
    for i in range(break_idx - below_streak, break_idx):
        ratio = volumes[i] / ma120_vol[i]
        if ratio < min_ratio:
            min_ratio = ratio

    # 阶段4: 涨幅计算
    break_close = closes[break_idx]
    before_close = closes[break_idx - below_streak] if break_idx - below_streak >= 0 else closes[max(0, break_idx - 30)]
    total_change = (break_close - before_close) / before_close * 100

    # 最近N天涨幅
    recent_change = (closes[-1] - closes[break_idx]) / closes[break_idx] * 100 if break_idx < n - 1 else 0

    return {
        "code": code,
        "name": name,
        "below_days": below_streak,           # 缩量天数
        "min_ratio": round(min_ratio, 2),     # 缩量期最低量比
        "break_ratio": round(volumes[break_idx] / ma120_vol[break_idx], 2),  # 突破日量比
        "break_close": round(closes[break_idx], 2),   # 突破日收盘
        "close": round(closes[-1], 2),                # 最新收盘
        "change_before": round(total_change, 1),      # 缩量期涨幅
        "change_after": round(recent_change, 1),      # 突破后涨幅
        "volume_now": round(volumes[-1] / ma120_vol[-1], 2) if ma120_vol[-1] else 0,  # 当前量比
        "break_date": str(klines[break_idx]['date'])[:10],  # 突破日期
    }


def main():
    parser = argparse.ArgumentParser(description="成交量形态扫描：缩量后放量突破MA120")
    parser.add_argument("--market", default="all", help="市场: all/sz/sh/688/30/60/00")
    parser.add_argument("--min-below", type=int, default=10, help="最小缩量天数 (默认10)")
    parser.add_argument("--volume-ratio", type=float, default=1.2, help="放量阈值倍率 (默认1.2)")
    parser.add_argument("--check-days", type=int, default=5, help="检查最近N天内突破 (默认5)")
    parser.add_argument("--workers", type=int, default=20, help="并发线程数 (默认20)")
    parser.add_argument("--save", action="store_true", help="保存结果到CSV/JSON")
    parser.add_argument("--max-results", type=int, default=0, help="只显示前N条 (0=全部)")
    args = parser.parse_args()

    stocks = get_stock_list(args.market)
    label = (f"缩量≥{args.min_below}d+突破MA120×{args.volume_ratio}"
             f"+近{args.check_days}d")

    print(f"\n📋 成交量形态扫描 | {label} | {len(stocks)}只\n")

    def check(code, name):
        return check_volume_pattern(
            code, name,
            min_below_days=args.min_below,
            volume_ratio=args.volume_ratio,
            check_days=args.check_days,
        )

    results, errors = scan_all(stocks, check, workers=args.workers, label=label)

    if not results:
        print("❌ 无命中")
        return

    # 按突破量比降序排列
    results.sort(key=lambda r: r["break_ratio"], reverse=True)

    # 打印表格
    display = results[:args.max_results] if args.max_results > 0 else results
    print(f"\n{'代码':>10s} {'名称':>8s} {'缩量天':>5s} {'最低量':>6s} "
          f"{'突破量':>6s} {'突破价':>7s} {'现价':>7s} {'缩量期%':>7s} {'突破后%':>7s} {'当前量':>6s} {'突破日':>10s}")
    print("-" * 85)
    for r in display:
        print(f"{r['code']:>10s} {r['name']:>8s} {r['below_days']:>5d} {r['min_ratio']:>5.2f}x "
              f"{r['break_ratio']:>5.2f}x {r['break_close']:>7.2f} {r['close']:>7.2f} "
              f"{r['change_before']:>+6.1f}% {r['change_after']:>+6.1f}% "
              f"{r['volume_now']:>5.2f}x {r['break_date']:>10s}")

    if args.max_results > 0 and len(results) > args.max_results:
        print(f"... 共 {len(results)} 只，仅显示前 {args.max_results} 只")

    print(f"\n✅ 共命中 {len(results)} 只 (异常: {errors})")

    # 保存
    if args.save:
        csv_columns = ["代码", "名称", "缩量天数", "最低量比", "突破量比",
                       "突破价", "现价", "缩量期涨幅%", "突破后涨幅%", "当前量比", "突破日期"]
        def csv_rows(r):
            return [
                r["code"], r["name"], r["below_days"], f"{r['min_ratio']:.2f}x",
                f"{r['break_ratio']:.2f}x", r["break_close"], r["close"],
                f"{r['change_before']:+.1f}%", f"{r['change_after']:+.1f}%",
                f"{r['volume_now']:.2f}x", r["break_date"],
            ]
        save_results(results, "缩量放量突破MA120",
                     csv_columns=csv_columns, csv_rows_fn=csv_rows)


if __name__ == "__main__":
    main()
