#!/usr/bin/env python3
"""
科技板块逐步缩量扫描器
============================
条件：
1. 科技相关板块（软件、半导体、人工智能、消费电子、芯片、机器人、科技等）
2. 最近一个月（约20个交易日）成交量逐日递减趋势
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from base import get_stock_list, fetch_klines_list, scan_all, save_results


def is_tech_related(name: str) -> bool:
    """判断股票名称是否科技相关"""
    tech_keywords = [
        '软件', '信息', '科技', '电子', '通信', '智能', '数据', '网络',
        '芯片', '半导', '光电', '计算', '云', '数码', '微', '芯',
        '集成', '传感', '激光', '显示', '半导体', '存储', '5G',
        '机器', '自动', '探测', '精密', '新材', '纳米',
    ]
    return any(kw in name for kw in tech_keywords)


def check_volume_declining(code: str, name: str, days: int = 20) -> dict | None:
    """检查最近N天成交量是否呈逐步递减趋势"""
    klines = fetch_klines_list(code, count=30)
    if not klines or len(klines) < days:
        return None

    recent = klines[-days:]
    volumes = [k["volume"] for k in recent]

    if any(v <= 0 for v in volumes):
        return None

    n = len(volumes)
    x = list(range(n))
    x_mean = sum(x) / n
    v_mean = sum(volumes) / n

    numerator = sum((x[i] - x_mean) * (volumes[i] - v_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return None

    slope = numerator / denominator
    if slope >= 0:
        return None

    early_avg = sum(volumes[:5]) / 5
    late_avg = sum(volumes[-5:]) / 5
    latest_vol = volumes[-1]

    if early_avg <= 0:
        return None

    shrink_ratio = late_avg / early_avg
    if shrink_ratio >= 0.75:
        return None
    if latest_vol >= late_avg:
        return None

    declining_days = sum(1 for i in range(1, n) if volumes[i] < volumes[i - 1])
    decline_pct = declining_days / (n - 1) * 100
    if decline_pct < 60:
        return None

    return {
        "code": code,
        "name": name,
        "slope": slope,
        "early_vol": early_avg,
        "late_vol": late_avg,
        "latest_vol": latest_vol,
        "shrink_ratio": shrink_ratio,
        "decline_pct": decline_pct,
        "declining_days": declining_days,
        "total_days": n,
        "early_date": recent[0]["date"],
        "late_date": recent[-1]["date"],
        "close": recent[-1]["close"],
    }


def main():
    print(f"{'=' * 60}")
    print(f"  科技板块逐步缩量扫描")
    print(f"  条件: 最近20日成交量逐步递减，缩量>=25%")
    print(f"{'=' * 60}")

    all_stocks = get_stock_list()
    tech_stocks = [(c, n) for c, n in all_stocks if is_tech_related(n)]
    print(f"   名称含科技关键词: {len(tech_stocks)} 只")

    results, _ = scan_all(tech_stocks, check_volume_declining, workers=20,
                          label="科技缩量扫描", exclude_st=False)

    if results:
        results.sort(key=lambda x: x['shrink_ratio'])
        print(f"\n{'代码':12s} {'名称':8s} {'收盘':>8s} {'缩量比':>8s} {'递减天':>6s} {'递减%':>6s} {'最早量':>12s} {'最新量':>12s}")
        print("-" * 85)
        for r in results:
            print(f"{r['code']:12s} {r['name']:8s} ¥{r['close']:>7.2f} "
                  f"{r['shrink_ratio']:>7.1%} {r['declining_days']:>4d}/{r['total_days']:>2d} "
                  f"{r['decline_pct']:>5.0f}% {r['early_vol']:>11.0f} {r['latest_vol']:>11.0f}")

        save_results(results, "科技缩量",
                     csv_columns=["股票代码", "股票名称", "收盘价", "缩量比", "递减天数", "总天数",
                                  "递减占比%", "最早5日均量", "最新5日均量", "最新量", "日期范围"],
                     csv_rows_fn=lambda r: [r["code"], r["name"], f"{r['close']:.2f}",
                                            f"{r['shrink_ratio']:.3f}", r["declining_days"], r["total_days"],
                                            f"{r['decline_pct']:.0f}", f"{r['early_vol']:.0f}", f"{r['late_vol']:.0f}",
                                            f"{r['latest_vol']:.0f}", f"{r['early_date']}~{r['late_date']}"])


if __name__ == "__main__":
    main()
