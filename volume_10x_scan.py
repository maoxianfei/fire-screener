#!/usr/bin/env python3
"""
10倍放量 — 全市场A股扫描器
============================
条件：今日成交量 >= 前一日成交量的N倍
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from base import get_stock_list, get_client, scan_all, save_results


def check_10x_volume(code: str, name: str, ratio_threshold: float = 10.0) -> dict | None:
    """检查最新一天成交量是否 >= 前一天的 ratio_threshold 倍"""
    raw_code = code.replace("sh", "").replace("sz", "")
    try:
        client = get_client()
        df = client.bars(symbol=raw_code, frequency=4, offset=30)
        if df is None or len(df) < 3:
            return None

        today = df.iloc[-1]
        yesterday = df.iloc[-2]

        today_vol = float(today.get("vol", 0) if "vol" in today.index else today.get("volume", 0))
        yest_vol = float(yesterday.get("vol", 0) if "vol" in yesterday.index else yesterday.get("volume", 0))

        if yest_vol <= 0:
            return None

        ratio = today_vol / yest_vol
        if ratio < ratio_threshold:
            return None

        today_date = str(today.get("datetime", ""))[:10]
        today_close = float(today.get("close", 0))
        today_change = (today_close / float(yesterday.get("close", 1)) - 1) * 100

        return {
            'code': code,
            'name': name,
            'date': today_date,
            'close': today_close,
            'change_pct': today_change,
            'today_vol': today_vol,
            'yest_vol': yest_vol,
            'vol_ratio': ratio,
        }
    except Exception:
        return None


def main():
    ratio_threshold = 10.0
    if len(sys.argv) > 1:
        try:
            ratio_threshold = float(sys.argv[1])
        except ValueError:
            pass

    print(f"{'=' * 60}")
    print(f"  10倍放量 — 全市场A股扫描")
    print(f"  条件: 今日成交量 >= 前一日的 {ratio_threshold:.0f} 倍")
    print(f"{'=' * 60}")

    stock_list = get_stock_list()
    results, _ = scan_all(stock_list, lambda c, n: check_10x_volume(c, n, ratio_threshold),
                          workers=20, label=f"{ratio_threshold:.0f}倍放量")

    if results:
        results.sort(key=lambda x: x['vol_ratio'], reverse=True)
        print(f"\n{'代码':12s} {'名称':8s} {'收盘':>8s} {'涨跌%':>7s} {'量比':>8s} {'今量':>14s} {'昨量':>14s}")
        print("-" * 85)
        for r in results:
            print(f"{r['code']:12s} {r['name']:8s} ¥{r['close']:>7.2f} "
                  f"{r['change_pct']:>+6.1f}% {r['vol_ratio']:>7.1f}x "
                  f"{r['today_vol']:>13.0f} {r['yest_vol']:>13.0f}")

        save_results(results, f"{ratio_threshold:.0f}倍放量",
                     csv_columns=["股票代码", "股票名称", "收盘价", "涨跌%", "量比", "今日成交量", "昨日成交量", "日期"],
                     csv_rows_fn=lambda r: [r["code"], r["name"], f"{r['close']:.2f}",
                                            f"{r['change_pct']:.1f}", f"{r['vol_ratio']:.1f}",
                                            f"{r['today_vol']:.0f}", f"{r['yest_vol']:.0f}", r["date"]])


if __name__ == "__main__":
    main()
