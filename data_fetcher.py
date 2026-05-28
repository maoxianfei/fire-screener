"""
A股 K线数据拉取 (mootdx)
========================
- fetch_klines(): 拉取单只股票K线
- get_stock_list(): 获取全市场A股列表
- fetch_current_prices(): 批量获取最新收盘价
"""

import threading
from mootdx.quotes import Quotes

# K线周期映射
_FREQ_MAP = {"daily": 9, "weekly": 5, "monthly": 6}

# Thread-local client，每个线程复用一个连接
_local = threading.local()


def _get_client() -> Quotes:
    """获取当前线程的 mootdx client（懒初始化，复用连接）"""
    if not hasattr(_local, "client"):
        _local.client = Quotes.factory(market="std")
    return _local.client


def fetch_klines(
    code: str,
    period: str = "daily",
    count: int = 120,
) -> list[dict]:
    """
    拉取单只A股K线数据

    Args:
        code: 6位股票代码
        period: "daily" | "weekly" | "monthly"
        count: 拉取数量

    Returns:
        按时间升序排列的K线列表, 每项:
        {"date": "YYYY-MM-DD", "open": float, "high": float,
         "low": float, "close": float, "volume": float}
    """
    client = _get_client()
    raw = client.bars(symbol=code, frequency=_FREQ_MAP.get(period, 9), offset=count)

    if raw is None or len(raw) == 0:
        return []

    klines = []
    for _, row in raw.iterrows():
        dt = str(row.get("datetime", ""))
        date = dt[:10] if dt else ""
        if not date:
            continue
        klines.append({
            "date": date,
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "close": float(row.get("close", 0)),
            "volume": float(row.get("vol", 0)),
        })

    klines.sort(key=lambda k: k["date"])
    return klines


def get_stock_list() -> list[tuple[str, str]]:
    """
    获取全市场A股列表 (沪深主板 + 科创/创业板 + 北交所)

    Returns:
        [(code, name), ...]
    """
    client = _get_client()
    results = []

    # 沪市: 60xxxx(主板) + 688xxx(科创板)
    sh = client.stocks(market=1)
    if sh is not None and len(sh) > 0:
        mask = sh["code"].str.match(r"^60\d{4}$") | sh["code"].str.match(r"^688\d{3}$")
        for _, row in sh[mask].iterrows():
            results.append((row["code"], row["name"]))

    # 深市: 00xxxx(主板) + 300xxx(创业板) + 8xxxxx/4xxxxx(北交所)
    sz = client.stocks(market=0)
    if sz is not None and len(sz) > 0:
        mask = (
            sz["code"].str.match(r"^00\d{4}$")
            | sz["code"].str.match(r"^30\d{4}$")
            | sz["code"].str.match(r"^8\d{5}$")
            | sz["code"].str.match(r"^4\d{5}$")
        )
        for _, row in sz[mask].iterrows():
            results.append((row["code"], row["name"]))

    results.sort(key=lambda x: x[0])
    return results


def fetch_current_prices(
    codes: list[str],
    max_workers: int = 10,
) -> dict[str, float]:
    """
    批量获取最新收盘价

    Args:
        codes: 股票代码列表
        max_workers: 并发数

    Returns:
        {code: price, ...}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    prices: dict[str, float] = {}

    def _get_one(code: str) -> tuple[str, float]:
        try:
            client = _get_client()
            df = client.bars(symbol=code, frequency=9, offset=1)
            if df is not None and len(df) > 0:
                p = float(df.iloc[-1]["close"])
                if p > 0:
                    return (code, p)
        except Exception:
            pass
        return (code, 0.0)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_get_one, c): c for c in codes}
        done = 0
        for fut in as_completed(futures):
            code, price = fut.result()
            if price > 0:
                prices[code] = price
            done += 1
            if done % 500 == 0:
                print(f"    价格采集进度: {done}/{len(codes)} (已获取 {len(prices)} 只)")

    print(f"    价格采集完成: {len(prices)}/{len(codes)} 只")
    return prices
