#!/usr/bin/env python3
"""二次筛选：对周线命中的股票，检查最近10天日线是否出现指定形态"""
import csv
import json
import sys
from data_fetcher import fetch_klines

# 读取周线筛选结果
csv_path = "output/一轮_阳阴阴阴阴阳_weekly_20260603.csv"
stocks = []
with open(csv_path, encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        code = row['股票代码'].strip()
        name = row['股票名称'].strip().replace('\x00', '')
        price = row['最新收盘价'].strip()
        if code and price:
            stocks.append({'code': code, 'name': name, 'price': price})

print(f"周线命中股票: {len(stocks)} 只")

# 形态定义
patterns = {
    '100001': '阳阴阴阴阴阳',
    '1010001': '阳阴阳阴阴阴阳'
}

def check_pattern_in_window(klines, pattern):
    """检查K线序列中最近10天是否出现过指定形态"""
    n = len(pattern)
    # 最近10天的K线
    recent_10 = klines[-10:] if len(klines) >= 10 else klines
    
    for start in range(len(recent_10) - n + 1):
        window = recent_10[start:start + n]
        if len(window) < n:
            continue
        matched = True
        for k, p in zip(window, pattern):
            is_up = k['close'] >= k['open']
            expected_up = (p == '1')
            if is_up != expected_up:
                matched = False
                break
        if matched:
            return True, window[-1]['date']
    return False, None

results = []
errors = []

for i, stock in enumerate(stocks):
    code = stock['code']
    name = stock['name']
    
    if (i + 1) % 50 == 0:
        print(f"进度: {i+1}/{len(stocks)}")
    
    try:
        klines = fetch_klines(code, period='daily', count=20)
        if not klines or len(klines) < 6:
            continue
        
        for pattern, desc in patterns.items():
            matched, end_date = check_pattern_in_window(klines, pattern)
            if matched:
                results.append({
                    'code': code,
                    'name': name,
                    'price': stock['price'],
                    'pattern': pattern,
                    'pattern_desc': desc,
                    'end_date': end_date
                })
    except Exception as e:
        errors.append(f"{code}: {e}")

# 按形态分组输出
print(f"\n{'='*60}")
print(f"二次筛选完成！")
print(f"周线 100001 命中: {len(stocks)} 只")
print(f"日线 100001/1010001 命中: {len(results)} 只")
if errors:
    print(f"异常: {len(errors)} 只")
print(f"{'='*60}\n")

# 按形态分组
for pattern, desc in patterns.items():
    matched = [r for r in results if r['pattern'] == pattern]
    if matched:
        print(f"日线形态 {pattern} ({desc}): {len(matched)} 只")
        print(f"{'代码':8s} {'名称':10s} {'最新价':>8s}  {'形态结束日':12s}")
        print("-" * 50)
        for r in sorted(matched, key=lambda x: float(x['price'])):
            print(f"{r['code']:8s} {r['name']:10s} ¥{r['price']:>8s}  {r['end_date']}")
        print()

# 同时命中两个形态的
both = {}
for r in results:
    key = r['code']
    if key not in both:
        both[key] = {'code': r['code'], 'name': r['name'], 'price': r['price'], 'patterns': []}
    both[key]['patterns'].append(r['pattern'])

dual = [v for v in both.values() if len(v['patterns']) > 1]
if dual:
    print(f"同时命中两个形态: {len(dual)} 只")
    for d in dual:
        print(f"  {d['code']} {d['name']} ¥{d['price']}  形态: {', '.join(d['patterns'])}")

# 保存完整结果
with open('output/二次筛选_周线日线联合.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n详细结果已保存: output/二次筛选_周线日线联合.json")
