#!/usr/bin/env python3
"""
主力吸筹 全市场A股扫描器
============================
条件：最新一根K线有主力进场信号
支持日线/周线/月线维度，支持板块过滤
"""

import argparse
import sys
import os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(__file__))

from base import get_stock_list, fetch_klines, zhuli_xichou, scan_all, save_results


PERIOD_MAP = {
    'daily':   {'frequency': 4, 'label': '日线', 'min_klines': 60, 'default_count': 150, 'signal_window_days': 30},
    'weekly':  {'frequency': 5, 'label': '周线', 'min_klines': 40, 'default_count': 100, 'signal_window_days': 90},
    'monthly': {'frequency': 6, 'label': '月线', 'min_klines': 24, 'default_count': 60,  'signal_window_days': 180},
}


def check_xichou(code: str, name: str, frequency: int = 4, count: int = 150,
                 min_klines: int = 60, signal_window_days: int = 30) -> dict | None:
    """检查单只股票是否有主力吸筹信号"""
    df = fetch_klines(code, count=count, frequency=frequency)
    if df is None or len(df) < min_klines:
        return None

    df = zhuli_xichou(df)
    last = df.iloc[-1]
    if last['zlxc_jinchang'] <= 0:
        return None

    window_ago = (datetime.now() - timedelta(days=signal_window_days)).strftime("%Y-%m-%d")
    window_signals = df[(df['date'] >= window_ago) & (df['zlxc_jinchang'] > 0)]

    return {
        'code': code,
        'name': name,
        'signal_date': last['date'],
        'close': float(last['close']),
        'var5': float(last['zlxc_var5']),
        'jinchang': float(last['zlxc_jinchang']),
        'window_signal_count': len(window_signals),
    }


def main():
    from datetime import datetime

    parser = argparse.ArgumentParser(description='主力吸筹全市场扫描器')
    parser.add_argument('--period', '-p', choices=['daily', 'weekly', 'monthly'], default='daily')
    parser.add_argument('--market', '-m', default='all')
    parser.add_argument('--count', '-c', type=int, default=None)
    parser.add_argument('--workers', '-w', type=int, default=20)
    parser.add_argument('--window', '-W', type=int, default=None)
    args = parser.parse_args()

    period_cfg = PERIOD_MAP[args.period]
    frequency = period_cfg['frequency']
    period_label = period_cfg['label']
    min_klines = period_cfg['min_klines']
    default_count = period_cfg['default_count']
    signal_window_days = args.window or period_cfg['signal_window_days']
    count = args.count or default_count

    market_labels = {
        'all': '全市场', 'sh': '沪市', 'sz': '深市',
        '688': '科创板', '30': '创业板', '60': '沪主板', '00': '深主板',
    }
    market_label = market_labels.get(args.market, args.market)

    print(f"{'=' * 60}")
    print(f"  主力吸筹 — {market_label}{period_label}扫描")
    print(f"  条件: 最新一根{period_label}有主力进场信号")
    print(f"{'=' * 60}")

    stock_list = get_stock_list(args.market)

    def check(code, name):
        return check_xichou(code, name, frequency, count, min_klines, signal_window_days)

    results, _ = scan_all(stock_list, check, workers=args.workers,
                          label=f"{market_label}{period_label} 主力吸筹")

    if results:
        results.sort(key=lambda x: x['var5'], reverse=True)
        window_label = f"近{signal_window_days}天信号"
        print(f"\n{'代码':12s} {'名称':8s} {'收盘':>8s} {'信号日':12s} {'VAR5':>10s} {'吸筹强度':>10s} {window_label:>10s}")
        print("-" * 80)
        for r in results:
            print(f"{r['code']:12s} {r['name']:8s} ¥{r['close']:>7.2f} "
                  f"{r['signal_date']:12s} {r['var5']:>10.4f} {r['jinchang']:>10.4f} {r['window_signal_count']:>10d}")

        market_tag = args.market if args.market != 'all' else '全市场'
        save_results(results, f"主力吸筹_{market_tag}_{args.period}",
                     csv_columns=["股票代码", "股票名称", "收盘价", "信号日期", "VAR5", "吸筹强度", window_label],
                     csv_rows_fn=lambda r: [r["code"], r["name"], f"{r['close']:.2f}",
                                            r["signal_date"], f"{r['var5']:.4f}", f"{r['jinchang']:.4f}",
                                            r["window_signal_count"]])


if __name__ == "__main__":
    main()
