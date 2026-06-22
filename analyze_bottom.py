"""分析股票是否为高位下来后底部抬高形态"""
import sys
sys.path.insert(0, '.')
from data_fetcher import fetch_klines

stocks = [
    ("002251", "步步高"),
    ("002557", "洽洽食品"),
    ("002594", "比亚迪"),
    ("002867", "周大生"),
    ("300761", "立华股份"),
    ("600622", "光大嘉宝"),
    ("600655", "豫园股份"),
    ("601066", "中信建投"),
    ("603683", "晶华新材"),
]

print("="*70)
print("  高位下跌 → 底部抬高 形态分析")
print("="*70)

results = []

for code, name in stocks:
    try:
        # 获取120天日线数据
        klines = fetch_klines(code, period="daily", count=120)
        if not klines or len(klines) < 60:
            print(f"{code} {name}: 数据不足")
            continue
        
        closes = [k['close'] for k in klines]
        
        # 1. 找历史高点（前60-120天内）
        early_prices = closes[:60]
        high_point = max(early_prices)
        high_idx = early_prices.index(high_point)
        
        # 2. 找近期低点（最近30-60天内）
        recent_lows = closes[-60:]
        low_point = min(recent_lows)
        low_idx = len(closes) - 60 + recent_lows.index(low_point)
        
        # 3. 从高点到低点的跌幅
        drop_pct = (low_point - high_point) / high_point * 100
        
        # 4. 检查最近30天是否有底部抬高迹象
        # 把最近30天分成3个10天区间，看最低点是否逐步抬高
        last_30 = closes[-30:]
        seg1_low = min(last_30[:10])
        seg2_low = min(last_30[10:20])
        seg3_low = min(last_30[20:])
        
        # 底部抬高条件：后面区间的低点 > 前面区间的低点
        bottom_rising = seg2_low > seg1_low * 0.98 and seg3_low > seg2_low * 0.98
        
        # 5. 当前价格相对高点的位置
        current = closes[-1]
        from_high = (current - high_point) / high_point * 100
        
        # 6. 从低点反弹幅度
        from_low = (current - low_point) / low_point * 100
        
        # 判断是否符合"高位下来底部抬高"
        is_candidate = (
            drop_pct < -15 and  # 从高位下跌超过15%
            bottom_rising and  # 底部逐步抬高
            from_high < -10 and  # 当前仍低于高点10%以上
            from_low > 5  # 从低点反弹超过5%
        )
        
        if is_candidate:
            results.append({
                'code': code,
                'name': name,
                'high': round(high_point, 2),
                'low': round(low_point, 2),
                'drop': round(drop_pct, 1),
                'current': round(current, 2),
                'from_high': round(from_high, 1),
                'from_low': round(from_low, 1),
                'seg1': round(seg1_low, 2),
                'seg2': round(seg2_low, 2),
                'seg3': round(seg3_low, 2),
            })
        
        print(f"\n{code} {name}:")
        print(f"  高点: ¥{high_point:.2f} → 低点: ¥{low_point:.2f} (跌幅{drop_pct:.1f}%)")
        print(f"  当前: ¥{current:.2f} (距高点{from_high:.1f}%, 距低点+{from_low:.1f}%)")
        print(f"  近30天底部: {seg1_low:.2f} → {seg2_low:.2f} → {seg3_low:.2f}")
        print(f"  底部抬高: {'✓ 是' if bottom_rising else '✗ 否'}")
        
    except Exception as e:
        print(f"{code} {name}: 错误 - {e}")

print("\n" + "="*70)
print("  符合「高位下跌 → 底部抬高」的股票：")
print("="*70)

if results:
    # 按反弹幅度排序
    results.sort(key=lambda x: x['from_low'], reverse=True)
    for r in results:
        print(f"\n✅ {r['code']} {r['name']}")
        print(f"   高点 ¥{r['high']} → 低点 ¥{r['low']} (跌{r['drop']}%)")
        print(f"   当前 ¥{r['current']} (距高{r['from_high']}%, 已反弹+{r['from_low']}%)")
        print(f"   底部: ¥{r['seg1']} → ¥{r['seg2']} → ¥{r['seg3']}")
else:
    print("\n❌ 未找到明显符合的股票")
