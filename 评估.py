#!/usr/bin/env python3
"""
个股综合评估工作流
==================
对单只股票运行全部指标，输出统一评估报告。

指标：形态扫描 + 主力吸筹 + 主力出货 + MA60趋势 + 成交量异动

用法：
    python 评估.py 600176
    python 评估.py sz000970 --period weekly
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from base import fetch_klines_list
from 指标.kline_pattern import HEXAGRAM_MAP, multi_pattern_match
from 指标.zhuli_xichou import zhuli_xichou, fetch_kline
from 指标.zhuli_chuhuo import zhuli_chuhuo
from 指标.ma import check_ma60_uptrend, check_ma_position
from 指标.volume import check_volume_anomaly

PERIOD_MAP = {"daily": 4, "weekly": 5, "monthly": 6}
PERIOD_CN = {"daily": "日线", "weekly": "周线", "monthly": "月线"}


def evaluate(code: str, period: str = "daily", count: int = 120):
    """对单只股票运行全指标评估"""
    freq = PERIOD_MAP[period]
    period_cn = PERIOD_CN[period]
    raw_code = code.replace("sh", "").replace("sz", "")
    display_code = f"sh{raw_code}" if raw_code[:1] in "56" else f"sz{raw_code}"

    print(f"{'=' * 60}")
    print(f"  {raw_code}  个股综合评估  ({period_cn})")
    print(f"{'=' * 60}")
    print()

    # ── 1. 形态扫描 ──
    print("─── 1. K线卦象形态 ───")
    df_k = fetch_kline(code, count=count, frequency=freq)
    klines = df_k.to_dict("records")
    results = multi_pattern_match(df_k, list(HEXAGRAM_MAP.keys()), lookback=30)
    # 按匹配结束日期降序排列
    results.sort(key=lambda r: r["match_end"], reverse=True)
    for r in results:
        gua = HEXAGRAM_MAP[r["pattern"]]
        print(f"  ✅ {gua} ({r['pattern']})  {r['match_start']} ~ {r['match_end']}")
    total = len(HEXAGRAM_MAP)
    print(f"  命中 {len(results)}/{total}")

    # ── 2. 主力吸筹 ──
    print("─── 2. 主力吸筹 ───")
    df_xc = zhuli_xichou(df_k.copy())
    recent = df_xc.tail(20)
    has_signal = False
    for _, row in recent.iterrows():
        if row['zlxc_jinchang'] > 0:
            print(f"  🔴 主力进场  {row['date']}  收盘¥{row['close']:.2f}  VAR5={row['zlxc_var5']:.2f}")
            has_signal = True
        elif row['zlxc_xipan'] > 0:
            print(f"  🟢 洗盘      {row['date']}  收盘¥{row['close']:.2f}  VAR5={row['zlxc_var5']:.2f}")
            has_signal = True
    if not has_signal:
        print(f"  ➖ 无信号（最近20日）")
    print()

    # ── 3. 主力出货 ──
    print("─── 3. 主力出货 ───")
    df_ch = zhuli_chuhuo(df_k.copy())
    recent = df_ch.tail(20)
    has_signal = False
    for _, row in recent.iterrows():
        if row['zlch_chuhuo'] > 0:
            print(f"  🟢 主力出货  {row['date']}  收盘¥{row['close']:.2f}  VAR5={row['zlch_var5']:.2f}")
            has_signal = True
        elif row['zlch_chengjie'] > 0:
            print(f"  🔴 洗盘      {row['date']}  收盘¥{row['close']:.2f}  VAR5={row['zlch_var5']:.2f}")
            has_signal = True
    if not has_signal:
        print(f"  ➖ 无信号（最近20日）")
    print()

    # ── 4. MA60 趋势 ──
    print("─── 4. MA60 趋势 ───")
    ma = check_ma60_uptrend(klines)
    if ma:
        print(f"  📈 连续 {ma['streak']} 天在MA60上方")
        print(f"  MA60: ¥{ma['ma60']:.2f}  收盘: ¥{ma['close']:.2f}  ({ma['pct']:+.1f}%)")
        flags = []
        if ma['passed_5d']:  flags.append("5d基础✅")
        if ma['passed_10d']: flags.append("10d确认✅")
        if ma['passed_20d']: flags.append("20d强势✅")
        print(f"  {' '.join(flags)}")
    else:
        print(f"  ➖ 数据不足（需至少80根K线）")
    print()

    # ── 5. 成交量异动 ──
    print("─── 5. 成交量异动 ───")
    vol = check_volume_anomaly(klines)
    if vol:
        icon = "📈" if vol['anomaly_type'] == "倍量" else "📉"
        print(f"  {icon} {vol['anomaly_type']}  {vol['date']}  量比={vol['vol_ratio']:.2f}")
        print(f"  收盘¥{vol['close']:.2f}  涨跌{vol['change_pct']:+.1f}%")
    else:
        print(f"  ➖ 正常（量比在0.70~1.30之间）")
    print()

    # ── 100分评分 ──
    print("─── 评分明细 ───")
    scores = {}
    total = 0
    last_date = klines[-1]["date"]
    recent_xc = df_xc.tail(20)
    recent_ch = df_ch.tail(20)

    def days_ago(d: str) -> int:
        for i, k in enumerate(reversed(klines)):
            if str(k["date"]) == d:
                return i
        return 999

    # 1. 卦象形态 (20分) — 按信号时间加权
    match_dates = [(r["match_end"], HEXAGRAM_MAP[r["pattern"]]) for r in results]
    recent7 = [d for d, _ in match_dates if days_ago(d) <= 7]
    recent20 = [d for d, _ in match_dates if 7 < days_ago(d) <= 20]
    if len(recent7) >= 2:
        scores["🀄 卦象"] = 20
    elif len(recent7) == 1:
        scores["🀄 卦象"] = 14
    elif len(recent20) >= 2:
        scores["🀄 卦象"] = 12
    elif len(recent20) == 1:
        scores["🀄 卦象"] = 8
    else:
        scores["🀄 卦象"] = 0
    scores["🀄 卦象"] = round(scores["🀄 卦象"])
    total += scores["🀄 卦象"]

    # 2/3. 主力吸筹 + 主力出货 — 按7天内信号频率评分
    xc_dates = recent_xc[recent_xc['zlxc_jinchang'] > 0]['date'].tolist()
    ch_dates = recent_ch[recent_ch['zlch_chuhuo'] > 0]['date'].tolist()
    xc_7d = sum(1 for d in xc_dates if days_ago(str(d)) <= 7)
    ch_7d = sum(1 for d in ch_dates if days_ago(str(d)) <= 7)

    # 吸筹: 1~3次满分(10), >3次权重0.5(5)
    if xc_7d == 0:
        xc_score = 0
    elif xc_7d <= 3:
        xc_score = 10
    else:
        xc_score = 5

    # 出货: 1~3次权重0.5(5), >3次满分(10)
    if ch_7d == 0:
        ch_score = 0
    elif ch_7d <= 3:
        ch_score = 5
    else:
        ch_score = 10

    scores["🔴 吸筹"] = xc_score
    scores["🟢 出货"] = ch_score
    total += xc_score + ch_score

    note_parts = []
    if xc_7d > 0:
        note_parts.append(f"吸筹{xc_7d}次{'→满分' if xc_7d<=3 else '→×0.5'}")
    if ch_7d > 0:
        note_parts.append(f"出货{ch_7d}次{'→×0.5' if ch_7d<=3 else '→满分'}")
    phase_note = " | ".join(note_parts) if note_parts else "无信号"

    # 4. MA60趋势 (40分)
    if ma:
        streak = ma['streak']
        if streak >= 20:
            scores["📈 MA60趋势"] = 40
        elif streak >= 10:
            scores["📈 MA60趋势"] = 28
        elif streak >= 5:
            scores["📈 MA60趋势"] = 16
        elif streak > 0:
            scores["📈 MA60趋势"] = 8
        else:
            scores["📈 MA60趋势"] = 0
    else:
        scores["📈 MA60趋势"] = 0
    total += scores["📈 MA60趋势"]

    # 5. 成交量异动 (20分) — 倍量10分 + 缩量10分
    # 倍量体系: 最近7天出现倍量, 10倍量→满分, 2倍量→0.2权重
    max_ratio_7d = 1.0
    for i in range(max(1, len(klines) - 7), len(klines)):
        prev_vol = klines[i - 1].get("volume", 0)
        cur_vol = klines[i].get("volume", 0)
        if prev_vol > 0:
            ratio = cur_vol / prev_vol
            if ratio > max_ratio_7d:
                max_ratio_7d = ratio
    beiliang_score = round(min(max_ratio_7d / 10, 1.0) * 10)

    # 缩量体系: 最新交易日缩量, 10日内最低得10分, 9日内得9分...
    today_vol = klines[-1].get("volume", 0)
    suo_liang_score = 0
    for n in range(10, 0, -1):
        if n <= len(klines):
            window = [k.get("volume", 0) for k in klines[-n:]]
            if today_vol <= min(window):
                suo_liang_score = n
                break

    scores["📊 倍量"] = beiliang_score
    scores["📊 缩量"] = suo_liang_score
    total += beiliang_score + suo_liang_score

    # ── 输出评分 ──
    print(f"\n  {'指标':<20} {'得分':>6}")
    print(f"  {'-'*28}")
    for k, v in scores.items():
        # 根据指标满分动态调整条形图
        if k == "📈 MA60趋势":
            bar = "█" * (v // 8) + "░" * (5 - v // 8)
        else:
            bar = "█" * (v // 4) + "░" * (5 - v // 4)
        print(f"  {k:<20} {v:>3}   {bar}")
    if phase_note:
        print(f"  {'↳ 7天统计':<20} {phase_note.strip():>20}")
    print(f"  {'-'*28}")
    print(f"  {'总分':<20} {total:>3}/100")

    if total >= 70:
        status = "🟢 偏多"
    elif total >= 40:
        status = "🟡 中性"
    else:
        status = "🔴 偏空"
    print(f"  {'判定':<20} {status}")
    print()


def main():
    parser = argparse.ArgumentParser(description="个股综合评估工作流")
    parser.add_argument("code", help="股票代码，如 600176 或 sz000970")
    parser.add_argument("--period", "-p", default="daily",
                        choices=list(PERIOD_MAP.keys()),
                        help="K线周期 (默认 daily)")
    parser.add_argument("--count", type=int, default=200,
                        help="获取K线根数 (默认 200)")
    args = parser.parse_args()

    evaluate(args.code, args.period, args.count)


if __name__ == "__main__":
    main()
