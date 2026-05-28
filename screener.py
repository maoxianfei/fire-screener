"""
K线阴阳形态全市场筛选器
========================
一轮：全市场K线形态扫描
二轮：量价双规则确认

用法:
  # 全流程（一轮+二轮）
  python screener.py --pattern 阳阳阴阴阳 --period weekly --start 2025-01-01

  # 只跑一轮
  python screener.py --pattern 阳阳阴阴阳 --period weekly --start 2025-01-01 --step 1

  # 只跑二轮（需指定一轮CSV）
  python screener.py --step 2 --input output/一轮_阳阳阴阴阳_weekly_20250101.csv

  # 加价格区间过滤
  python screener.py --pattern 阳阳阴阴阳 --period weekly --start 2025-01-01 --price-min 5 --price-max 50
"""

import argparse
import csv
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime

from data_fetcher import fetch_klines, get_stock_list, fetch_current_prices

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
LOCK = threading.Lock()


# ============================================================
# 形态解析
# ============================================================

def parse_pattern(s: str) -> list[int]:
    """阴阳形态字符串 → [0,1,0,1,...]"""
    s = s.strip()
    if all(c in "01" for c in s):
        return [int(c) for c in s]
    result = []
    for ch in s:
        if ch == "阳":
            result.append(1)
        elif ch == "阴":
            result.append(0)
        else:
            raise ValueError(f"无效字符 '{ch}'，只支持 阴/阳 或 0/1")
    if not result:
        raise ValueError("形态不能为空")
    return result


def pattern_to_str(p: list[int]) -> str:
    """[0,1,0] → '阴阳阴'"""
    return "".join("阳" if b else "阴" for b in p)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class PatternHit:
    """单次形态命中"""
    start_date: str
    end_date: str


@dataclass
class Round1Result:
    """一轮扫描结果"""
    code: str
    name: str
    total_matches: int
    hits: list[PatternHit] = field(default_factory=list)
    latest_close: float = 0.0
    error: str = ""


@dataclass
class Round2Result:
    """二轮筛选结果"""
    code: str
    name: str
    vol_pass: bool = False
    price_pass: bool = False
    vol_ratio: float = 0.0
    price_diff: float = 0.0
    error: str = ""


# ============================================================
# 形态匹配核心
# ============================================================

def scan_pattern(
    klines: list[dict],
    pattern: list[int],
    start_date: str,
    end_date: str,
) -> list[PatternHit]:
    """在K线日期范围内滑动窗口匹配形态"""
    plen = len(pattern)
    if plen == 0 or len(klines) < plen:
        return []

    in_range = [k for k in klines if start_date <= k["date"] <= end_date]
    if len(in_range) < plen:
        return []

    bits = [1 if k["close"] >= k["open"] else 0 for k in in_range]
    hits = []
    for i in range(len(bits) - plen + 1):
        if bits[i : i + plen] == pattern:
            hits.append(PatternHit(
                start_date=in_range[i]["date"],
                end_date=in_range[i + plen - 1]["date"],
            ))
    return hits


# ============================================================
# 一轮：全市场形态扫描
# ============================================================

def calc_kline_count(period: str, start: str, end: str) -> int:
    """根据周期和日期范围自动计算K线数量"""
    sd = datetime.strptime(start, "%Y-%m-%d")
    ed = datetime.strptime(end, "%Y-%m-%d")
    days = (ed - sd).days
    if period == "daily":
        return int(days * 0.7) + 30
    elif period == "weekly":
        return max(days // 7, 1) + 20
    else:
        months = (ed.year - sd.year) * 12 + (ed.month - sd.month)
        return max(months, 1) + 12


def scan_one(
    code: str, name: str,
    pattern: list[int], period: str,
    start_date: str, end_date: str, count: int,
) -> Round1Result:
    """单股形态扫描"""
    try:
        klines = fetch_klines(code, period=period, count=count)
        if not klines:
            return Round1Result(code=code, name=name, total_matches=0, error="无数据")
        hits = scan_pattern(klines, pattern, start_date, end_date)
        return Round1Result(
            code=code, name=name,
            total_matches=len(hits), hits=hits,
            latest_close=klines[-1]["close"],
        )
    except Exception as e:
        return Round1Result(code=code, name=name, total_matches=0, error=str(e)[:100])


def run_round1(
    pattern: list[int],
    period: str,
    start_date: str,
    end_date: str,
    price_min: float = 0,
    price_max: float = 9999,
    workers: int = 12,
    count: int = None,
) -> tuple[list[Round1Result], str]:
    """
    一轮：全市场形态扫描

    Returns:
        (结果列表, CSV路径)
    """
    period_label = {"daily": "日线", "weekly": "周线", "monthly": "月线"}.get(period, period)
    if count is None:
        count = calc_kline_count(period, start_date, end_date)

    print(f"\n{'='*60}")
    print(f"  一轮：全市场形态扫描")
    print(f"  形态: {pattern_to_str(pattern)} ({len(pattern)}根)")
    print(f"  周期: {period_label}  日期: {start_date} ~ {end_date}")
    print(f"  K线数: {count}  并发: {workers}")
    print(f"{'='*60}")

    # 1. 获取股票列表
    print(f"\n  [1/3] 获取A股列表...")
    stocks = get_stock_list()
    print(f"  全市场: {len(stocks)} 只")

    # 2. 价格预过滤
    if price_min > 0 or price_max < 9999:
        print(f"\n  [2/3] 价格过滤: ¥{price_min} ~ ¥{price_max}")
        codes = [c for c, _ in stocks]
        prices = fetch_current_prices(codes, max_workers=10)
        stocks = [(c, n) for c, n in stocks if price_min <= prices.get(c, 0) <= price_max]
        print(f"  保留: {len(stocks)} 只")
    else:
        print(f"\n  [2/3] 跳过价格过滤")

    # 3. 并发扫描
    print(f"\n  [3/3] 形态扫描 ({len(stocks)} 只)...")
    results: list[Round1Result] = []
    done = [0]
    t0 = time.time()

    def task(code, name):
        r = scan_one(code, name, pattern, period, start_date, end_date, count)
        with LOCK:
            done[0] += 1
            if done[0] % 500 == 0:
                elapsed = time.time() - t0
                speed = done[0] / elapsed if elapsed > 0 else 0
                hits = sum(1 for x in results if x.total_matches > 0)
                print(f"    {done[0]}/{len(stocks)} | 命中{hits} | {speed:.0f}只/秒")
        return r

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(task, c, n): (c, n) for c, n in stocks}
        for fut in as_completed(futures):
            results.append(fut.result())

    elapsed = time.time() - t0
    hits_list = [r for r in results if r.total_matches > 0]
    hits_list.sort(key=lambda r: (-r.total_matches, r.code))

    # 统计
    total_hits = sum(r.total_matches for r in hits_list)
    errors = sum(1 for r in results if r.error)

    print(f"\n  扫描完成: {elapsed:.1f}s")
    print(f"  命中: {len(hits_list)} 只 ({len(hits_list)/max(len(stocks),1)*100:.1f}%)")
    print(f"  总信号: {total_hits} 次")
    print(f"  异常: {errors} 只")

    # 多次命中
    multi = [r for r in hits_list if r.total_matches >= 2]
    if multi:
        print(f"\n  多次命中 ({len(multi)} 只):")
        for r in multi[:20]:
            dates = "; ".join(h.end_date for h in r.hits)
            print(f"    {r.code} {r.name}  {r.total_matches}次  {dates}")

    # 导出CSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    csv_name = f"一轮_{pattern_to_str(pattern)}_{period}_{timestamp}.csv"
    csv_path = os.path.join(OUTPUT_DIR, csv_name)

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["股票代码", "股票名称", "命中次数",
                         "形态结束日期(所有)", "信号区间(所有)",
                         "最新收盘价", "备注"])
        for r in hits_list:
            writer.writerow([
                r.code, r.name, r.total_matches,
                "; ".join(h.end_date for h in r.hits),
                "; ".join(f"{h.start_date}~{h.end_date}" for h in r.hits),
                round(r.latest_close, 2), "",
            ])
        for r in results:
            if r.error:
                writer.writerow([r.code, r.name, 0, "", "", 0, r.error])

    print(f"\n  CSV: {csv_path}")
    return results, csv_path


# ============================================================
# 二轮：量价双规则筛选
# ============================================================

def check_round2(code: str, config: dict) -> Round2Result:
    """单股量价双规则检查"""
    try:
        klines = fetch_klines(code, period="daily", count=config["daily_count"])
    except Exception as e:
        return Round2Result(code=code, name="", error=f"拉取异常:{e}")

    if not klines or len(klines) < 80:
        return Round2Result(code=code, name="", error=f"数据不足({len(klines) if klines else 0})")

    n = len(klines)

    # 规则1：最近N天至少1天成交量 > M日均量
    vw = config["vol_window"]
    vol_ma = sum(k["volume"] for k in klines[-vw:]) / vw if n >= vw else 0
    lookback = min(config["vol_lookback"], n)
    recent_vols = [k["volume"] for k in klines[-lookback:]]
    vol_pass = any(v > vol_ma for v in recent_vols) if vol_ma > 0 else False
    avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 0
    vol_ratio = avg_vol / vol_ma * 100 if vol_ma > 0 else 0

    # 规则2：最新收盘价 >= P日均线 × tolerance
    pm = config["price_ma"]
    ma_price = sum(k["close"] for k in klines[-pm:]) / pm if n >= pm else 0
    latest_close = klines[-1]["close"]
    tol = config["price_tolerance"]
    price_pass = latest_close >= ma_price * tol if ma_price > 0 else False
    price_diff = (latest_close - ma_price) / ma_price * 100 if ma_price > 0 else 0

    return Round2Result(
        code=code, name="",
        vol_pass=vol_pass, price_pass=price_pass,
        vol_ratio=vol_ratio, price_diff=price_diff,
    )


def run_round2(input_csv: str, workers: int = 10) -> str:
    """二轮：读取一轮CSV，执行量价双规则筛选"""
    # 默认配置
    config = {
        "daily_count": 150,
        "vol_window": 120,
        "vol_lookback": 25,
        "price_ma": 70,
        "price_tolerance": 0.95,
    }

    # 读取一轮数据
    with open(input_csv, "r", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    pending = []
    for row in rows[1:]:
        code = row[0].strip()
        name = row[1].strip().replace("\x00", "")
        note = row[6].strip() if len(row) > 6 else ""
        if note:
            continue
        pending.append((code, name, row[3] if len(row) > 3 else ""))

    total = len(pending)
    if total == 0:
        print("  无待检查股票")
        return ""

    print(f"\n{'='*60}")
    print(f"  二轮：量价双规则筛选")
    print(f"  规则1: 最近{config['vol_lookback']}天至少1天量 > {config['vol_window']}日均量")
    print(f"  规则2: 收盘 ≥ {config['price_ma']}日均线 × {config['price_tolerance']}")
    print(f"  待检查: {total} 只  并发: {workers}")
    print(f"{'='*60}")

    results: dict[str, Round2Result] = {}
    done = [0]
    pass_count = [0]
    t0 = time.time()

    def task(code, name, _):
        r = check_round2(code, config)
        r.name = name
        with LOCK:
            done[0] += 1
            if r.vol_pass and r.price_pass:
                pass_count[0] += 1
            if done[0] % 100 == 0:
                print(f"    [{done[0]}/{total}] 通过{pass_count[0]}", end="\r")
        return r

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(task, c, n, d): c for c, n, d in pending}
        for fut in as_completed(futures):
            r = fut.result()
            results[r.code] = r

    elapsed = time.time() - t0
    print()

    # 统计
    pass_both = sum(1 for r in results.values() if r.vol_pass and r.price_pass)
    fail_vol = sum(1 for r in results.values() if not r.vol_pass and r.price_pass)
    fail_price = sum(1 for r in results.values() if r.vol_pass and not r.price_pass)
    fail_both = sum(1 for r in results.values() if not r.vol_pass and not r.price_pass)
    errors = sum(1 for r in results.values() if r.error)

    print(f"\n  完成: {elapsed:.1f}s")
    print(f"  双通过: {pass_both} ({pass_both/max(len(results),1)*100:.1f}%)")
    print(f"  仅量不达标: {fail_vol}")
    print(f"  仅价不达标: {fail_price}")
    print(f"  量价双杀: {fail_both}")

    # 导出CSV
    timestamp = datetime.now().strftime("%Y%m%d")
    pattern_name = os.path.basename(input_csv).split("_")[1] if "_" in os.path.basename(input_csv) else "result"
    out_name = f"二轮_{pattern_name}_{timestamp}.csv"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    out_rows = [["股票代码", "股票名称", "命中次数", "形态结束日期",
                 "信号区间", "最新收盘价", "5周量比%", "价差%", "状态"]]

    for row in rows[1:]:
        code = row[0].strip()
        if code not in results:
            continue
        r = results[code]
        if not (r.vol_pass and r.price_pass):
            continue
        out_rows.append([
            code, r.name, row[2] if len(row) > 2 else "",
            row[3] if len(row) > 3 else "",
            row[4] if len(row) > 4 else "",
            row[5] if len(row) > 5 else "",
            f"{r.vol_ratio:.1f}", f"{r.price_diff:+.1f}", "通过",
        ])

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(out_rows)

    # 多次命中
    multi = [r for r in out_rows[1:] if int(r[2]) >= 2]
    if multi:
        print(f"\n  多次命中 + 双通过 ({len(multi)} 只):")
        for r in multi[:20]:
            print(f"    {r[0]} {r[1]}  命中{r[2]}次 | 量比{r[6]}% | 价差{r[7]}%")

    print(f"\n  CSV: {out_path}")
    return out_path


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="K线阴阳形态全市场筛选器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 全流程
  python screener.py --pattern 阳阳阴阴阳 --period weekly --start 2025-01-01

  # 价格区间过滤
  python screener.py --pattern 阳阳阴阴阳 --period weekly --start 2025-01-01 --price-min 5 --price-max 50

  # 只跑一轮
  python screener.py --pattern 阳阳阴阴阳 --period weekly --start 2025-01-01 --step 1

  # 只跑二轮
  python screener.py --step 2 --input output/一轮_阳阳阴阴阳_weekly_20250101.csv
        """,
    )
    parser.add_argument("--pattern", help="阴阳形态, 如: 阳阳阴阴阳 或 00101")
    parser.add_argument("--period", choices=["daily", "weekly", "monthly"], default="weekly",
                        help="K线周期 (默认 weekly)")
    parser.add_argument("--start", default="2025-01-01", help="搜索起始日期 (默认 2025-01-01)")
    parser.add_argument("--end", default=date.today().strftime("%Y-%m-%d"), help="搜索结束日期 (默认今天)")
    parser.add_argument("--price-min", type=float, default=0, help="最低股价 (默认 0)")
    parser.add_argument("--price-max", type=float, default=9999, help="最高股价 (默认 9999)")
    parser.add_argument("--workers", type=int, default=12, help="并发线程数 (默认 12)")
    parser.add_argument("--count", type=int, default=None, help="K线数量 (默认自动计算)")
    parser.add_argument("--step", choices=["1", "2", "all"], default="all",
                        help="执行步骤: 1=一轮, 2=二轮, all=全流程 (默认 all)")
    parser.add_argument("--input", help="二轮输入CSV路径 (仅 --step 2 时使用)")

    args = parser.parse_args()

    r1_csv = None

    if args.step in ("1", "all"):
        if not args.pattern:
            parser.error("一轮扫描需要 --pattern 参数")

        pattern = parse_pattern(args.pattern)
        print(f"形态: {args.pattern} → {pattern_to_str(pattern)} ({len(pattern)}根)")

        _, r1_csv = run_round1(
            pattern=pattern,
            period=args.period,
            start_date=args.start,
            end_date=args.end,
            price_min=args.price_min,
            price_max=args.price_max,
            workers=args.workers,
            count=args.count,
        )

    if args.step in ("2", "all"):
        input_csv = args.input or r1_csv
        if not input_csv:
            # 自动找最新一轮文件
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            r1_files = sorted([
                f for f in os.listdir(OUTPUT_DIR)
                if f.startswith("一轮_") and f.endswith(".csv")
            ], reverse=True)
            if not r1_files:
                print("  未找到一轮CSV，请先执行 --step 1 或指定 --input")
                sys.exit(1)
            input_csv = os.path.join(OUTPUT_DIR, r1_files[0])
            print(f"  自动选择: {r1_files[0]}")

        if not os.path.exists(input_csv):
            print(f"  文件不存在: {input_csv}")
            sys.exit(1)

        run_round2(input_csv, workers=args.workers)


if __name__ == "__main__":
    main()
