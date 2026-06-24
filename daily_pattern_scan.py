#!/usr/bin/env python3
"""
日线形态筛选器
=============
策略: 在最近N天内寻找指定的日线阴阳形态
定义: 1=阳线(close>open), 0=阴线(close<=open)
"""

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from base import get_stock_list, fetch_klines, scan_all, save_results, print_table


def check_pattern(code: str, name: str, pattern: str = "101000",
                  lookback: int = 30, price_min: float = 0,
                  price_max: float = 9999) -> dict | None:
    """检查单只股票是否匹配日线形态"""
    df = fetch_klines(code, count=lookback + 10)
    if df is None or len(df) < lookback:
        return None

    # 价格过滤
    last_close = float(df.iloc[-1]['close'])
    if last_close < price_min or last_close > price_max:
        return None

    recent = df.tail(lookback)
    daily_pattern = "".join("1" if r['close'] > r['open'] else "0" for _, r in recent.iterrows())

    if pattern not in daily_pattern:
        return None

    idx = daily_pattern.find(pattern)
    matched = recent.iloc[idx:idx + len(pattern)]

    return {
        "code": code,
        "name": name,
        "match_start": matched.iloc[0]['date'],
        "match_end": matched.iloc[-1]['date'],
        "daily_pattern": daily_pattern,
        "match_pos": idx,
        "last_close": last_close,
        "last_date": df.iloc[-1]['date'],
    }


def main():
    parser = argparse.ArgumentParser(description='日线形态筛选器')
    parser.add_argument('pattern', nargs='?', default='101000',
                        help='目标形态(二进制), 如 "001000110010001101"')
    parser.add_argument('--lookback', '-l', type=int, default=30)
    parser.add_argument('--price-min', type=float, default=0)
    parser.add_argument('--price-max', type=float, default=9999)
    parser.add_argument('--market', '-m', default='all')
    parser.add_argument('--workers', '-w', type=int, default=15)
    args = parser.parse_args()

    print(f"{'=' * 60}")
    print(f"  日线形态筛选")
    print(f"  目标形态: {args.pattern} ({len(args.pattern)}根K线)")
    print(f"  回看天数: {args.lookback}")
    print(f"  价格区间: ¥{args.price_min} ~ ¥{args.price_max}")
    print(f"  时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'=' * 60}")

    stock_list = get_stock_list(args.market)
    print(f"   非ST股票: {len(stock_list)} 只")

    def check(code, name):
        return check_pattern(code, name, args.pattern, args.lookback,
                             args.price_min, args.price_max)

    results, _ = scan_all(stock_list, check, workers=args.workers,
                          label=f"日线形态 {args.pattern}")

    if results:
        results.sort(key=lambda x: x["name"])
        print(f"\n{'代码':12s} {'名称':10s} {'收盘':>8s} {'匹配区间':>25s} {'日线形态'}")
        print("-" * 90)
        for r in results:
            print(f"{r['code']:12s} {r['name']:10s} ¥{r['last_close']:>7.2f} "
                  f"{r['match_start']}~{r['match_end']} {r['daily_pattern']}")

        extra = {}
        if args.price_min > 0 or args.price_max < 9999:
            extra = {"price": f"{args.price_min}-{args.price_max}"}
        save_results(results, f"日线形态{args.pattern}",
                     csv_columns=["股票代码", "股票名称", "最新收盘价", "匹配开始", "匹配结束", "匹配位置", "日线形态"],
                     csv_rows_fn=lambda r: [r["code"], r["name"], f"{r['last_close']:.2f}",
                                            r["match_start"], r["match_end"], r["match_pos"], r["daily_pattern"]],
                     extra_tags=extra)


if __name__ == "__main__":
    main()
