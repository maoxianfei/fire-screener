#!/usr/bin/env python3
"""
三重过滤: 周线101000 + 主力吸筹 + 最近10天倍量
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from base import fetch_klines, zhuli_xichou, save_results


def load_weekly_hits(json_path: str = None) -> list[dict]:
    if json_path is None:
        json_path = os.path.join(os.path.dirname(__file__), 'output', '周线形态101000_20260613.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_stock(item: dict) -> dict | None:
    code = item['code']
    name = item['name']

    df = fetch_klines(code, count=150)
    if df is None or len(df) < 60:
        return None

    # 条件1: 主力吸筹信号(最近5天)
    df = zhuli_xichou(df)
    recent5 = df.tail(5)
    signal_days = recent5[recent5['zlxc_jinchang'] > 0]
    if len(signal_days) == 0:
        return None

    last_signal = signal_days.iloc[-1]

    # 条件2: 最近10天有倍量(成交量>=前一日2倍)
    recent10 = df.tail(10)
    vol = recent10['volume'].values
    vol_prev = np.roll(vol, 1)
    vol_prev[0] = np.nan

    beiliang_mask = vol >= vol_prev * 2
    beiliang_idx = np.where(beiliang_mask)[0]

    if len(beiliang_idx) == 0:
        return None

    bl_pos = beiliang_idx[-1]
    bl_row = recent10.iloc[bl_pos]
    bl_ratio = vol[bl_pos] / vol_prev[bl_pos] if vol_prev[bl_pos] > 0 else 0

    return {
        'code': code,
        'name': name,
        'weekly_pattern': item.get('weekly_pattern', ''),
        'weekly_match': f"{item.get('match_start', '')}~{item.get('match_end', '')}",
        'xc_date': last_signal['date'],
        'xc_close': float(last_signal['close']),
        'xc_var5': float(last_signal['zlxc_var5']),
        'bl_date': bl_row['date'],
        'bl_vol_ratio': round(bl_ratio, 1),
        'bl_close': float(bl_row['close']),
        'last_close': float(df.iloc[-1]['close']),
        'last_date': df.iloc[-1]['date'],
    }


def main():
    weekly_hits = load_weekly_hits()
    print(f"{'=' * 65}")
    print(f"  三重过滤: 周线101000 + 主力吸筹 + 倍量")
    print(f"  周线命中: {len(weekly_hits)} 只")
    print(f"{'=' * 65}\n")

    results = []
    errors = 0
    done = 0
    total = len(weekly_hits)

    with ThreadPoolExecutor(max_workers=15) as pool:
        futures = {pool.submit(check_stock, item): item for item in weekly_hits}
        for fut in as_completed(futures):
            done += 1
            try:
                r = fut.result()
                if r:
                    results.append(r)
                    print(f"  ✅ [{done}/{total}] {r['name']}({r['code']}) "
                          f"吸筹:{r['xc_date']} VAR5:{r['xc_var5']:.1f} "
                          f"倍量:{r['bl_date']} {r['bl_vol_ratio']}x")
            except Exception:
                errors += 1
            if done % 100 == 0:
                print(f"   进度: {done}/{total} | 命中: {len(results)}")

    print(f"\n{'=' * 65}")
    print(f"  三重过滤完成！ {total} → {len(results)} 只")
    print(f"{'=' * 65}\n")

    if results:
        results.sort(key=lambda x: x['xc_var5'], reverse=True)
        print(f"{'代码':12s} {'名称':8s} {'收盘':>7s} {'吸筹日':>10s} {'VAR5':>8s} {'倍量日':>10s} {'倍数':>5s} {'周线'}")
        print("-" * 90)
        for r in results:
            print(f"{r['code']:12s} {r['name']:8s} {r['last_close']:>7.2f} "
                  f"{r['xc_date']:>10s} {r['xc_var5']:>8.1f} "
                  f"{r['bl_date']:>10s} {r['bl_vol_ratio']:>4.1f}x {r['weekly_pattern']}")

        save_results(results, "三重过滤",
                     csv_columns=["股票代码", "股票名称", "最新收盘", "吸筹日期", "吸筹VAR5",
                                  "倍量日期", "倍量倍数", "倍量收盘", "周线形态"],
                     csv_rows_fn=lambda r: [r["code"], r["name"], f"{r['last_close']:.2f}",
                                            r["xc_date"], f"{r['xc_var5']:.1f}",
                                            r["bl_date"], f"{r['bl_vol_ratio']}", f"{r['bl_close']:.2f}",
                                            r["weekly_pattern"]])


if __name__ == "__main__":
    main()
