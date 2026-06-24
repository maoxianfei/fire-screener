"""
fire-earth 共享基础设施
========================
线程安全客户端、数据获取、指标、扫描框架、输出
"""

import csv
import json
import os
import re
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd
import numpy as np

ssl._create_default_https_context = ssl._create_unverified_context

# ═══════════════════════════════════════════
# 线程安全的 mootdx 客户端
# ═══════════════════════════════════════════

_thread_local = threading.local()


def get_client():
    if not hasattr(_thread_local, "client"):
        from mootdx.quotes import Quotes
        _thread_local.client = Quotes.factory(market="std")
    return _thread_local.client


# ═══════════════════════════════════════════
# 股票列表
# ═══════════════════════════════════════════

def get_stock_list(market: str = 'all') -> list[tuple[str, str]]:
    """
    获取A股列表
    market: all | sh | sz | 688 | 30 | 60 | 00
    返回: [(code, name), ...]  code格式: sh600519 / sz000001
    """
    from mootdx.quotes import Quotes
    client = Quotes.factory(market="std")
    results = []

    for mkt in [1, 0]:
        df = client.stocks(market=mkt)
        if df is None or len(df) == 0:
            continue
        for _, row in df.iterrows():
            code = str(row["code"])
            name = str(row["name"]).replace("\x00", "")
            if mkt == 1:
                prefix = 'sh'
                valid = re.match(r"^(60\d{4}|688\d{3})$", code)
            else:
                prefix = 'sz'
                valid = re.match(r"^(00\d{4}|30\d{4})$", code)

            if not valid:
                continue

            if market == '688' and not code.startswith('688'):
                continue
            elif market == '30' and not code.startswith('30'):
                continue
            elif market == '60' and not code.startswith('60'):
                continue
            elif market == '00' and not code.startswith('00'):
                continue
            elif market == 'sh' and mkt != 1:
                continue
            elif market == 'sz' and mkt != 0:
                continue

            results.append((f"{prefix}{code}", name))
    return sorted(set(results))


# ═══════════════════════════════════════════
# K线数据获取
# ═══════════════════════════════════════════

def fetch_klines(code: str, count: int = 120, frequency: int = 4) -> pd.DataFrame | None:
    """
    从mootdx获取K线数据，统一返回DataFrame
    code: sh600519 / sz000001 格式
    frequency: 4=日线, 5=周线, 6=月线
    返回列: date, open, high, low, close, volume
    """
    raw_code = code.replace("sh", "").replace("sz", "")
    try:
        client = get_client()
        df = client.bars(symbol=raw_code, frequency=frequency, offset=count)
        if df is None or len(df) == 0:
            return None

        df = df.copy()
        df['date'] = df['datetime'].astype(str).str[:10]
        for col in ['open', 'close', 'high', 'low']:
            df[col] = df[col].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df[['date', 'open', 'high', 'low', 'close', 'volume']]
    except Exception:
        return None


def fetch_klines_list(code: str, count: int = 120, frequency: int = 4) -> list[dict]:
    """返回list[dict]格式的K线数据，兼容旧代码"""
    df = fetch_klines(code, count, frequency)
    if df is None:
        return []
    return df.to_dict('records')


# ═══════════════════════════════════════════
# 指标
# ═══════════════════════════════════════════

def sma(series: pd.Series, n: int, m: int) -> pd.Series:
    """通达信 SMA(X, N, M) 递推加权移动平均"""
    result = pd.Series(np.nan, index=series.index)
    first_valid = series.first_valid_index()
    if first_valid is None:
        return result
    start = series.index.get_loc(first_valid)
    result.iloc[start] = series.iloc[start]
    for i in range(start + 1, len(series)):
        if np.isnan(series.iloc[i]):
            result.iloc[i] = result.iloc[i - 1]
        else:
            result.iloc[i] = (m * series.iloc[i] + (n - m) * result.iloc[i - 1]) / n
    return result


def zhuli_xichou(df: pd.DataFrame) -> pd.DataFrame:
    """
    主力吸筹指标
    返回新增列: zlxc_var5, zlxc_jinchang, zlxc_xipan
    """
    low = df['low']
    open_ = df['open']
    close = df['close']
    high = df['high']

    avg_price = (low + open_ + close + high) / 4
    var1 = avg_price.shift(1)
    diff = low - var1
    numerator = sma(diff.abs(), 13, 1)
    denominator = sma(diff.clip(lower=0), 10, 1)
    var2 = numerator / denominator.replace(0, np.nan)
    var3 = var2.ewm(span=10, adjust=False).mean()
    var4 = low.rolling(window=33, min_periods=1).min()
    conditional = pd.Series(np.where(low <= var4, var3, 0), index=df.index)
    var5 = conditional.ewm(span=3, adjust=False).mean()

    var5_prev = var5.shift(1)
    jinchang = pd.Series(np.where(var5 > var5_prev, var5, 0), index=df.index)
    xipan = pd.Series(np.where(var5 < var5_prev, var5, 0), index=df.index)

    df = df.copy()
    df['zlxc_var5'] = var5
    df['zlxc_jinchang'] = jinchang
    df['zlxc_xipan'] = xipan
    return df


# ═══════════════════════════════════════════
# 日线转周线
# ═══════════════════════════════════════════

def daily_to_weekly(klines: list[dict]) -> list[dict]:
    """日线list[dict]转周线list[dict]"""
    if not klines:
        return []
    df = pd.DataFrame(klines)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.isocalendar().year
    df["week"] = df["date"].dt.isocalendar().week
    weekly = []
    for (y, w), g in df.groupby(["year", "week"]):
        weekly.append({
            "date": g.iloc[0]["date"].strftime("%Y-%m-%d"),
            "open": float(g.iloc[0]["open"]),
            "close": float(g.iloc[-1]["close"]),
            "high": float(g["high"].max()),
            "low": float(g["low"].min()),
            "volume": float(g["volume"].sum()),
        })
    weekly.sort(key=lambda w: w["date"])
    return weekly


def daily_to_weekly_df(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame日线转周线DataFrame"""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.isocalendar().year
    df["week"] = df["date"].dt.isocalendar().week
    weekly = []
    for (y, w), g in df.groupby(["year", "week"]):
        weekly.append({
            "date": g.iloc[0]["date"].strftime("%Y-%m-%d"),
            "open": float(g.iloc[0]["open"]),
            "close": float(g.iloc[-1]["close"]),
            "high": float(g["high"].max()),
            "low": float(g["low"].min()),
            "volume": float(g["volume"].sum()),
        })
    return pd.DataFrame(weekly).sort_values("date").reset_index(drop=True)


# ═══════════════════════════════════════════
# 扫描框架
# ═══════════════════════════════════════════

def scan_all(stocks: list[tuple[str, str]], check_fn, workers: int = 20,
             label: str = '', exclude_st: bool = True) -> tuple[list[dict], int]:
    """
    全市场扫描框架
    stocks: [(code, name), ...]
    check_fn: fn(code, name) -> dict | None
    返回: (results, errors)
    """
    if exclude_st:
        stocks = [(c, n) for c, n in stocks if "ST" not in n.upper()]

    t0 = time.time()
    results = []
    errors = 0
    done = 0
    total = len(stocks)

    if label:
        print(f"\n📋 {label} 扫描中... ({total} 只)")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_fn, c, n): (c, n) for c, n in stocks}
        for fut in as_completed(futures):
            done += 1
            try:
                match = fut.result()
                if match:
                    results.append(match)
            except Exception:
                errors += 1
            if done % 500 == 0:
                elapsed = time.time() - t0
                print(f"   进度: {done}/{total} | 命中: {len(results)} | 耗时: {elapsed:.0f}s")

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  扫描完成！ {total} 只 | 命中: {len(results)} 只 | 异常: {errors} | 耗时: {elapsed:.0f}s")
    print(f"{'=' * 60}\n")

    return results, errors


# ═══════════════════════════════════════════
# 输出
# ═══════════════════════════════════════════

def save_results(results: list[dict], prefix: str, csv_columns: list[str] = None,
                 csv_rows_fn=None, extra_tags: dict = None):
    """
    保存结果到CSV和JSON
    prefix: 文件名前缀，如 "日线形态101000"
    csv_columns: CSV表头
    csv_rows_fn: fn(result) -> list  CSV每行数据
    extra_tags: 额外的文件名标签 {"key": "value"}
    """
    if not results:
        print("❌ 无结果，跳过保存")
        return

    os.makedirs("output", exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")

    tag = ""
    if extra_tags:
        tag = "_" + "_".join(f"{v}" for v in extra_tags.values() if v)

    csv_path = f"output/{prefix}_{today}{tag}.csv"
    json_path = f"output/{prefix}_{today}{tag}.json"

    if csv_columns and csv_rows_fn:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(csv_columns)
            for r in results:
                writer.writerow(csv_rows_fn(r))
        print(f"📄 CSV已保存: {csv_path}")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"📄 JSON已保存: {json_path}")


def print_table(results: list[dict], columns: list[tuple[str, str, str]], separator: str = "-"):
    """
    打印结果表格
    columns: [(key, label, fmt), ...]
      key: 字段名
      label: 表头
      fmt: 格式化字符串，如 ">8s", ">7.2f", ">+6.1f%"
    """
    if not results:
        return

    header = "".join(f"{label:{fmt}}" for _, label, fmt in columns)
    print(header)
    print(separator * max(len(header), 80))
    for r in results:
        row = ""
        for key, _, fmt in columns:
            val = r.get(key, "")
            if fmt.endswith('%'):
                real_fmt = fmt[:-1]
                row += f"{val:{real_fmt}}%"
            else:
                row += f"{val:{fmt}}"
        print(row)
