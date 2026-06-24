#!/usr/bin/env python3
"""
周线形态 + 主力吸筹 双重过滤
读取周线扫描结果，用主力吸筹指标过滤最近一周有信号的
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from base import fetch_klines, zhuli_xichou, save_results


def load_weekly_hits(json_path: str = None) -> list[dict]:
    """加载周线扫描结果"""
    if json_path is None:
        json_path = os.path.join(os.path.dirname(__file__), 'output', '周线形态101000_20260613.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_one(item: dict) -> dict | None:
    """检查单只股票是否满足周线形态+主力吸筹"""
    code = item['code']
    name = item['name']

    df = fetch_klines(code, count=150)
    if df is None or len(df) < 60:
        return None

    df = zhuli_xichou(df)
    recent = df.tail(5)
    signal_days = recent[recent['zlxc_jinchang'] > 0]

    if len(signal_days) == 0:
        return None

    last_signal = signal_days.iloc[-1]

    return {
        'code': code,
        'name': name,
        'weekly_pattern': item.get('weekly_pattern', ''),
        'weekly_match': f"{item.get('match_start', '')}~{item.get('match_end', '')}",
        'signal_date': last_signal['date'],
        'signal_close': float(last_signal['close']),
        'zlxc_var5': float(last_signal['zlxc_var5']),
        'zlxc_jinchang': float(last_signal['zlxc_jinchang']),
        'signal_count': len(signal_days),
    }


def main():
    from base import scan_all

    weekly_hits = load_weekly_hits()
    print(f"{'=' * 60}")
    print(f"  周线101000 + 主力吸筹 双重过滤")
    print(f"  周线命中: {len(weekly_hits)} 只")
    print(f"{'=' * 60}\n")

    results = []
    errors = 0
    done = 0
    total = len(weekly_hits)

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=15) as pool:
        futures = {pool.submit(check_one, item): item for item in weekly_hits}
        for fut in as_completed(futures):
            done += 1
            try:
                r = fut.result()
                if r:
                    results.append(r)
                    print(f"  ✅ [{done}/{total}] {r['name']}({r['code']}) 信号日:{r['signal_date']} VAR5:{r['zlxc_var5']:.4f}")
            except Exception:
                errors += 1
            if done % 100 == 0:
                print(f"   进度: {done}/{total} | 命中: {len(results)}")

    print(f"\n{'=' * 60}")
    print(f"  双重过滤完成！ {total} 只 → {len(results)} 只")
    print(f"{'=' * 60}\n")

    if results:
        results.sort(key=lambda x: x['zlxc_var5'], reverse=True)
        print(f"{'代码':12s} {'名称':8s} {'收盘':>8s} {'信号日':12s} {'VAR5':>10s} {'吸筹强度':>10s} {'周线形态'}")
        print("-" * 90)
        for r in results:
            print(f"{r['code']:12s} {r['name']:8s} ¥{r['signal_close']:>7.2f} "
                  f"{r['signal_date']:12s} {r['zlxc_var5']:>10.4f} {r['zlxc_jinchang']:>10.4f} {r['weekly_pattern']}")

        save_results(results, "周线101000_主力吸筹",
                     csv_columns=["股票代码", "股票名称", "信号收盘价", "信号日期", "VAR5", "吸筹强度",
                                  "信号次数", "周线形态", "周线匹配区间"],
                     csv_rows_fn=lambda r: [r["code"], r["name"], f"{r['signal_close']:.2f}",
                                            r["signal_date"], f"{r['zlxc_var5']:.4f}", f"{r['zlxc_jinchang']:.4f}",
                                            r["signal_count"], r["weekly_pattern"], r["weekly_match"]])


if __name__ == "__main__":
    main()
