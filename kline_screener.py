"""
K线阴阳形态筛选器
=================
全市场扫描指定K线阴阳形态（日线/周线/月线），支持历史日期范围滑动窗口搜索。

用法:
  python kline_screener.py --period weekly --pattern 阴阴阳阴阳阳阴阴阳 --start 2025-01-01 --end 2026-05-27
  python kline_screener.py --period daily --pattern 阳阳阴阳阳 --start 2026-01-01 --end 2026-05-27
  python kline_screener.py --period monthly --pattern 阴阳阳 --start 2024-01-01 --end 2026-05-27

参数:
  --period        K线周期: daily(日线) | weekly(周线) | monthly(月线)
  --pattern       阴阳形态, 中文输入, 如: 阴阴阳阴阳  (也支持01: 00101)
  --start         搜索起始日期 YYYY-MM-DD
  --end           搜索结束日期 YYYY-MM-DD (默认今天)
  --workers       并发线程数 (默认12)
  --count         K线数量 (默认自动计算: 日线=天数+30, 周线=周数+20, 月线=月数+12)
  --single        单股模式: --single 600519 (诊断调试用)
  --output        输出文件路径 (默认 output/kline_pattern_YYYYMMDD.csv)
  --price-min     最低股价过滤 (默认0=不限)
  --price-max     最高股价过滤 (默认9999=不限)
  --no-price-filter  跳过价格预过滤 (兼容旧行为)

阴阳判断规则:
  close >= open → 阳爻(1)
  close <  open → 阴爻(0)
"""

import argparse
import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime
from threading import Lock

from data_fetcher import fetch_klines
from hexagram_engine import KLine

# ─────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# 形态解析
# ─────────────────────────────────────────────

def parse_pattern(pattern_str: str) -> list[int]:
    """
    解析阴阳形态字符串为 0/1 列表。

    支持：
      - 中文: "阴阴阳阴阳阳"  → [0,0,1,0,1,1]
      - 01串: "001011"        → [0,0,1,0,1,1]

    Returns:
        list of 0/1
    """
    pattern_str = pattern_str.strip()
    if all(c in "01" for c in pattern_str):
        return [int(c) for c in pattern_str]
    result = []
    for ch in pattern_str:
        if ch == "阳":
            result.append(1)
        elif ch == "阴":
            result.append(0)
        else:
            raise ValueError(f"无效字符 '{ch}'，只支持 阴/阳 或 0/1")
    if not result:
        raise ValueError("形态不能为空")
    return result


def pattern_to_str(pattern: list[int]) -> str:
    """[0,1,0] → '阴阳阴'"""
    return "".join("阳" if b else "阴" for b in pattern)


# ─────────────────────────────────────────────
# 形态扫描核心
# ─────────────────────────────────────────────

@dataclass
class PatternHit:
    """单次形态命中"""
    start_date: str
    end_date: str
    actual: list[int]       # 实际0/1序列


@dataclass
class ScanResult:
    """单股扫描结果"""
    code: str
    name: str
    total_matches: int
    hits: list[PatternHit] = field(default_factory=list)
    latest_close: float = 0.0
    error: str = ""


def kline_to_bit(k: KLine) -> int:
    """实体方向判断: close >= open → 1(阳), else 0(阴)"""
    return 1 if k.close >= k.open else 0


def scan_pattern(
    klines: list[KLine],
    pattern: list[int],
    start_date: str,
    end_date: str,
) -> list[PatternHit]:
    """
    在 K 线列表的日期范围内，滑动窗口扫描形态匹配。

    Args:
        klines:     按时间升序排列的K线
        pattern:    目标0/1序列
        start_date: 搜索起始日期 "YYYY-MM-DD"
        end_date:   搜索结束日期 "YYYY-MM-DD"

    Returns:
        命中列表，每次命中包含区间和实际序列
    """
    plen = len(pattern)
    if plen == 0 or len(klines) < plen:
        return []

    # 截取日期范围内的K线
    in_range = [k for k in klines if start_date <= k.date <= end_date]
    if len(in_range) < plen:
        return []

    # 将K线转为阴阳bits
    bits = [kline_to_bit(k) for k in in_range]

    hits = []
    for i in range(len(bits) - plen + 1):
        window = bits[i: i + plen]
        if window == pattern:
            hits.append(PatternHit(
                start_date=in_range[i].date,
                end_date=in_range[i + plen - 1].date,
                actual=window,
            ))

    return hits


# ─────────────────────────────────────────────
# 单股扫描（线程任务）
# ─────────────────────────────────────────────

def scan_one(
    code: str,
    name: str,
    pattern: list[int],
    period: str,
    start_date: str,
    end_date: str,
    count: int,
) -> ScanResult:
    """单股完整扫描流程"""
    try:
        klines = fetch_klines(code, market="a", period=period, count=count)
        if not klines:
            return ScanResult(code=code, name=name, total_matches=0, error="无数据")

        latest_close = klines[-1].close
        hits = scan_pattern(klines, pattern, start_date, end_date)

        return ScanResult(
            code=code,
            name=name,
            total_matches=len(hits),
            hits=hits,
            latest_close=latest_close,
        )
    except Exception as e:
        return ScanResult(code=code, name=name, total_matches=0, error=str(e)[:100])


# ─────────────────────────────────────────────
# 全市场股票列表
# ─────────────────────────────────────────────

def get_all_stocks() -> list[tuple[str, str]]:
    """
    获取A股列表（仅沪深京普通股，排除ETF/指数/B股/可转债等）。

    过滤规则：
        SH market=1 → 仅 60xxxx(主板) + 68xxxx(科创板)
        SZ market=0 → 仅 00xxxx(主板) + 30xxxx(创业板)
        BJ         → 8xxxxx / 43xxxx / 83xxxx（北交所）

    Returns:
        [(code, name), ...]  6位代码 + 股票名称
    """
    from mootdx.quotes import Quotes
    client = Quotes.factory(market="std")

    # A股有效代码前缀（排除 900 B股/000 指数/399 指数/159 ETF/51xx ETF 等）
    SH_A_PREFIX = ("60", "68")
    SZ_A_PREFIX = ("00", "30")
    BJ_A_PREFIX = ("8", "43", "83")

    result = []
    for market_id, prefixes in [
        (1, SH_A_PREFIX),   # 上海
        (0, SZ_A_PREFIX),   # 深圳
    ]:
        df = client.stocks(market=market_id)
        if df is None or len(df) == 0:
            continue
        for _, row in df.iterrows():
            code = str(row.get("code", "")).strip()
            name = str(row.get("name", "")).strip()
            if not code or len(code) != 6:
                continue
            # 仅保留已知A股前缀
            if any(code.startswith(p) for p in prefixes):
                result.append((code, name))

    # 北交所 — mootdx 可能未收录；如果已有则不会重复添加
    bj_seen = {c for c, _ in result}
    for market_id, prefixes in [
        (0, BJ_A_PREFIX),   # BJ 通常归在 SZ market
    ]:
        df = client.stocks(market=market_id)
        if df is None or len(df) == 0:
            continue
        for _, row in df.iterrows():
            code = str(row.get("code", "")).strip()
            name = str(row.get("name", "")).strip()
            if not code or len(code) != 6:
                continue
            if code in bj_seen:
                continue
            if any(code.startswith(p) for p in prefixes):
                result.append((code, name))

    return result


# ─────────────────────────────────────────────
# 价格预过滤（拉K线前快速过滤股票池）
# ─────────────────────────────────────────────

def _get_one_close(code: str) -> tuple[str, float]:
    """
    获取单只股票最近收盘价（日线 count=1，与 data_fetcher.py 同通道）。
    在子线程中创建独立 client 避免连接冲突。
    """
    from mootdx.quotes import Quotes
    market = 1 if code.startswith(("6", "9")) else 0
    try:
        client = Quotes.factory(market="std")
        df = client.bars(symbol=code, frequency=9, offset=1)
        if df is not None and len(df) > 0:
            close = float(df.iloc[-1]["close"])
            if close > 0:
                return (code, close)
    except Exception:
        pass
    return (code, 0.0)


def fetch_all_prices(candidates: list[tuple[str, str]], max_workers: int = 10) -> dict[str, float]:
    """
    获取候选股票最近收盘价（mootdx 日线 count=1，与 K 线同 TCP 通道）。

    线程池并行拉取，默认 10 并发（避免 TDX 服务器过载）。

    Args:
        candidates: [(code, name), ...]  候选股票列表
        max_workers: 并发线程数

    Returns:
        {code: price, ...}  6位代码 → 最近收盘价
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    prices: dict[str, float] = {}
    if not candidates:
        return prices

    total = len(candidates)
    codes_only = [c for c, _ in candidates]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_get_one_close, c): c for c in codes_only}
        done = 0
        for fut in as_completed(futures):
            code, price = fut.result()
            if price > 0:
                prices[code] = price
            done += 1
            if done % 500 == 0:
                print(f"    价格采集进度: {done}/{total} (已获取 {len(prices)} 只)")

    if prices:
        print(f"    K线收盘价 获取 {len(prices)}/{total} 只报价")
    return prices


def filter_by_price(
    candidates: list[tuple[str, str]],
    prices: dict[str, float],
    price_min: float,
    price_max: float,
) -> list[tuple[str, str]]:
    """用价格区间过滤候选股票池。"""
    if price_min <= 0 and price_max >= 9999:
        return candidates

    kept = []
    no_price = 0
    for code, name in candidates:
        p = prices.get(code)
        if p is None:
            no_price += 1
            continue
        if price_min <= p <= price_max:
            kept.append((code, name))

    eliminated = len(candidates) - len(kept)
    pct = eliminated / len(candidates) * 100 if candidates else 0
    print(f"  价格过滤: ¥{price_min:.1f} ~ ¥{price_max:.1f} "
          f"→ 保留 {len(kept)} 只 (淘汰 {eliminated} 只, {pct:.1f}%)")
    if no_price > 0:
        print(f"    其中 {no_price} 只无报价数据被跳过")
    return kept


# ─────────────────────────────────────────────
# K线数量自动计算
# ─────────────────────────────────────────────

def calc_count(period: str, start_date: str, end_date: str) -> int:
    """
    根据周期和日期跨度自动计算需要的K线数量。

    - 日线: 自然天数 × 0.7 (约交易日) + 30根余量
    - 周线: 周数 + 20根余量
    - 月线: 月数 + 12根余量
    """
    sd = datetime.strptime(start_date, "%Y-%m-%d")
    ed = datetime.strptime(end_date, "%Y-%m-%d")
    days = (ed - sd).days
    months = (ed.year - sd.year) * 12 + (ed.month - sd.month)

    if period == "daily":
        return int(days * 0.7) + 30
    elif period == "weekly":
        return max(days // 7, 1) + 20
    else:  # monthly
        return max(months, 1) + 12


# ─────────────────────────────────────────────
# CSV 导出
# ─────────────────────────────────────────────

def save_csv(
    results: list[ScanResult],
    output_path: str,
    pattern: list[int],
    period: str,
    start_date: str,
    end_date: str,
) -> None:
    """将扫描结果保存为CSV"""
    hits = [r for r in results if r.total_matches > 0]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            f"# 形态: {pattern_to_str(pattern)}",
            f"周期: {period}",
            f"日期范围: {start_date} ~ {end_date}",
        ])
        writer.writerow([
            "股票代码", "股票名称", "命中次数",
            "命中开始日期(所有)", "命中结束日期(所有)", "实际形态(所有)",
            "最新收盘价", "备注",
        ])
        for r in sorted(hits, key=lambda x: -x.total_matches):
            writer.writerow([
                r.code,
                r.name,
                r.total_matches,
                "; ".join(h.start_date for h in r.hits),
                "; ".join(h.end_date for h in r.hits),
                "; ".join(pattern_to_str(h.actual) for h in r.hits),
                round(r.latest_close, 2),
                "",
            ])

    print(f"\n  📁 输出: {output_path}")
    print(f"     命中: {len(hits)} 只")


# ─────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────

def run_single(args, pattern: list[int]) -> None:
    """单股诊断模式"""
    code = args.single.strip().lstrip("sh").lstrip("sz")
    count = args.count if args.count is not None else calc_count(args.period, args.start, args.end)

    print(f"\n══ 单股诊断: {code} ══")
    print(f"  周期: {args.period}  形态: {pattern_to_str(pattern)}  日期: {args.start} ~ {args.end}")
    print(f"  拉取: {count}根\n")

    klines = fetch_klines(code, market="a", period=args.period, count=count)
    if not klines:
        print("  ❌ 无法获取K线数据")
        return

    print(f"  K线: {len(klines)}根  范围: {klines[0].date} ~ {klines[-1].date}")

    # 打印日期范围内K线的阴阳序列
    in_range = [k for k in klines if args.start <= k.date <= args.end]
    print(f"  范围内K线: {len(in_range)}根\n")

    if in_range:
        print("  ─ 范围内K线阴阳序列 ─")
        bits = [kline_to_bit(k) for k in in_range]
        labels = ["阳" if b else "阴" for b in bits]
        for i in range(0, len(in_range), 10):
            chunk = in_range[i: i + 10]
            chunk_labels = labels[i: i + 10]
            row_str = "  ".join(f"{c.date}{l}" for c, l in zip(chunk, chunk_labels))
            print(f"    {row_str}")

    hits = scan_pattern(klines, pattern, args.start, args.end)
    print(f"\n  ─ 形态 [{pattern_to_str(pattern)}] 检测 ─")
    if hits:
        print(f"  命中 {len(hits)} 次:")
        for i, h in enumerate(hits, 1):
            print(f"    #{i}  {h.start_date} ~ {h.end_date}  实际: {pattern_to_str(h.actual)}")
    else:
        print(f"  无命中（目标形态在日期范围内未出现）")

    print(f"\n  最新收盘: {klines[-1].close}  ({klines[-1].date})")


def run_full_scan(args, pattern: list[int]) -> None:
    """全市场扫描模式"""
    timestamp = datetime.now().strftime("%Y%m%d")
    period_label = {"daily": "日线", "weekly": "周线", "monthly": "月线"}.get(args.period, args.period)
    output_name = f"kline_pattern_{period_label}_{pattern_to_str(pattern)}_{timestamp}.csv"

    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(OUTPUT_DIR, output_name)

    # 自动计算K线数量（未手动指定时）
    count = args.count if args.count is not None else calc_count(args.period, args.start, args.end)
    # 是否启用价格过滤
    use_price_filter = not args.no_price_filter

    print(f"\n══ K线阴阳形态筛选 ══")
    print(f"  形态: {pattern_to_str(pattern)}  ({len(pattern)}根K线)")
    print(f"  周期: {period_label}  日期: {args.start} ~ {args.end}")
    if use_price_filter and (args.price_min > 0 or args.price_max < 9999):
        print(f"  价格: ¥{args.price_min:.1f} ~ ¥{args.price_max:.1f}")
    print(f"  拉取: {count}根{period_label}  |  并发: {args.workers} 线程\n")

    # ── [1] 获取股票列表 ──
    step = "1" if not use_price_filter else "1/4"
    print(f"  [{step}] 获取全市场股票列表...")
    stocks = get_all_stocks()
    print(f"  共 {len(stocks)} 只股票\n")

    # ── [2] 价格预过滤（拉K线前快速过滤）──
    if use_price_filter:
        print(f"  [2/4] 获取全市场实时行情...")
        all_prices = fetch_all_prices(stocks)
        if all_prices:
            print(f"  获取到 {len(all_prices)} 只有效报价")
            stocks = filter_by_price(stocks, all_prices, args.price_min, args.price_max)
            if not stocks:
                print("  ❌ 价格过滤后无候选股票，退出")
                return
        else:
            print(f"  ⚠  无法获取实时行情，跳过价格过滤")
        print()

    # ── [3] 并发扫描 ──
    step_no = "3/4" if use_price_filter else "2/3"
    print(f"  [{step_no}] 并发扫描 (每只拉取{count}根{period_label})...")
    results: list[ScanResult] = []
    lock = Lock()
    done = [0]

    def task(code: str, name: str) -> ScanResult:
        r = scan_one(code, name, pattern, args.period, args.start, args.end, count)
        with lock:
            done[0] += 1
            if done[0] % 500 == 0:
                print(f"    进度: {done[0]}/{len(stocks)} ({done[0]/len(stocks)*100:.1f}%)")
        return r

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(task, code, name): (code, name) for code, name in stocks}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                code, name = futures[fut]
                results.append(ScanResult(code=code, name=name, total_matches=0, error=str(e)[:80]))

    # ── [4] 统计 + 输出 ──
    hits_count = sum(1 for r in results if r.total_matches > 0)
    total_hits = sum(r.total_matches for r in results)
    error_count = sum(1 for r in results if r.error)
    hit_rate = hits_count / len(stocks) * 100 if stocks else 0

    final_step = "4/4" if use_price_filter else "3/3"
    print(f"\n  [{final_step}] 扫描完成")
    print(f"  ─────────────────────────────")
    print(f"  扫描总数: {len(stocks)} 只")
    print(f"  命中股票: {hits_count} 只  ({hit_rate:.1f}%)")
    print(f"  命中总次数: {total_hits} 次")
    print(f"  数据异常: {error_count} 只")

    # 多次命中
    multi = [(r.code, r.name, r.total_matches) for r in results if r.total_matches >= 2]
    if multi:
        multi.sort(key=lambda x: -x[2])
        print(f"\n  多次命中 ({len(multi)} 只):")
        for code, name, cnt in multi[:20]:
            print(f"    {code} {name}: {cnt} 次")

    # 保存CSV
    print(f"\n  保存结果...")
    save_csv(results, output_path, pattern, args.period, args.start, args.end)


def main():
    parser = argparse.ArgumentParser(
        description="K线阴阳形态全市场筛选器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 周线，9根形态，2025全年
  python kline_screener.py --period weekly --pattern 阴阴阳阴阳阳阴阴阳 --start 2025-01-01 --end 2026-05-27

  # 日线，5根形态，最近半年，只扫5~50元股票
  python kline_screener.py --period daily --pattern 阳阳阴阳阳 --start 2026-01-01 --price-min 5 --price-max 50

  # 周线，排除3元以下低价股
  python kline_screener.py --period weekly --pattern 阴阴阳阴阳 --start 2025-01-01 --price-min 3

  # 单股诊断
  python kline_screener.py --period weekly --pattern 阴阴阳阴阳 --start 2025-01-01 --single 600519

  # 手动指定K线数量（覆盖自动计算）
  python kline_screener.py --period daily --pattern 阳阳阳 --start 2026-01-01 --count 100

  # 跳过价格过滤（兼容旧行为）
  python kline_screener.py --period weekly --pattern 阴阴阳阴阳阳 --start 2025-01-01 --no-price-filter
        """,
    )
    parser.add_argument("--period", choices=["daily", "weekly", "monthly"],
                        default="weekly", help="K线周期")
    parser.add_argument("--pattern", required=True,
                        help="阴阳形态, 如: 阴阴阳阴阳阳阴阴阳 或 001011")
    parser.add_argument("--start", default="2025-01-01",
                        help="搜索起始日期 YYYY-MM-DD (默认 2025-01-01)")
    parser.add_argument("--end", default=date.today().strftime("%Y-%m-%d"),
                        help="搜索结束日期 YYYY-MM-DD (默认今天)")
    parser.add_argument("--workers", type=int, default=12,
                        help="并发线程数 (默认12)")
    parser.add_argument("--count", type=int, default=None,
                        help="每只股票拉取K线数量 (默认自动计算)")
    parser.add_argument("--single", default="",
                        help="单股诊断模式, 输入6位代码")
    parser.add_argument("--output", default="",
                        help="自定义输出文件路径")
    parser.add_argument("--price-min", type=float, default=0,
                        help="最低股价过滤 (默认0=不限)")
    parser.add_argument("--price-max", type=float, default=9999,
                        help="最高股价过滤 (默认9999=不限)")
    parser.add_argument("--no-price-filter", action="store_true",
                        help="跳过价格预过滤 (兼容旧行为)")

    args = parser.parse_args()

    # 解析形态
    try:
        pattern = parse_pattern(args.pattern)
    except ValueError as e:
        print(f"[错误] 形态解析失败: {e}")
        sys.exit(1)

    print(f"形态解析: {args.pattern} → {pattern_to_str(pattern)} ({len(pattern)}根K线)")

    # 验证日期
    try:
        datetime.strptime(args.start, "%Y-%m-%d")
        datetime.strptime(args.end, "%Y-%m-%d")
    except ValueError:
        print("[错误] 日期格式不正确，请用 YYYY-MM-DD")
        sys.exit(1)

    if args.start > args.end:
        print(f"[错误] start ({args.start}) 不能晚于 end ({args.end})")
        sys.exit(1)

    if args.single:
        run_single(args, pattern)
    else:
        run_full_scan(args, pattern)


if __name__ == "__main__":
    main()
