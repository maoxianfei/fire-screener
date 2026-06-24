#!/usr/bin/env python3
"""
fire-earth 统一入口
====================
CLI:  python run.py <scanner> [options]
API:  from run import scan; results = scan('daily-pattern', pattern='101000')
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from base import get_stock_list, scan_all

# ═══════════════════════════════════════════
# 扫描器注册表
# ═══════════════════════════════════════════

SCANNERS = {
    'daily-pattern': {
        'module': 'daily_pattern_scan',
        'func': 'check_pattern',
        'desc': '日线形态筛选',
        'params': {'pattern': '101000', 'lookback': 30, 'price_min': 0, 'price_max': 9999},
    },
    'weekly-pattern': {
        'module': 'weekly_pattern_scan',
        'func': 'check_weekly_pattern',
        'desc': '周线形态筛选',
        'params': {'pattern': '101000', 'lookback': 10},
    },
    'volume-breakout': {
        'module': 'volume_breakout',
        'func': 'check_breakout',
        'desc': '横盘放量突破',
        'params': {'max_range_ratio': 1.15},
    },
    '10x-volume': {
        'module': 'volume_10x_scan',
        'func': 'check_10x_volume',
        'desc': '10倍放量',
        'params': {'ratio_threshold': 10.0},
    },
    'xichou': {
        'module': 'full_xichou_scan',
        'func': 'check_xichou',
        'desc': '主力吸筹',
        'params': {'frequency': 4, 'count': 150, 'min_klines': 60, 'signal_window_days': 30},
    },
    'tech-decline': {
        'module': 'tech_volume_decline',
        'func': 'check_volume_declining',
        'desc': '科技板块缩量',
        'params': {'days': 20},
    },
}


def _load_check_fn(scanner_name: str):
    """动态加载扫描器的检查函数"""
    cfg = SCANNERS[scanner_name]
    mod = __import__(cfg['module'])
    return getattr(mod, cfg['func'])


def scan(scanner_name: str, market: str = 'all', workers: int = 20, **kwargs) -> list[dict]:
    """
    编程式调用入口
    scanner_name: 扫描器名称，见 SCANNERS
    market: all | sh | sz | 688 | 30 | 60 | 00
    **kwargs: 传递给扫描器的参数
    返回: 命中结果列表

    示例:
        results = scan('daily-pattern', pattern='101000', lookback=30, market='688')
        results = scan('xichou', period='daily', market='all')
        results = scan('volume-breakout', max_range_ratio=1.10)
    """
    if scanner_name not in SCANNERS:
        raise ValueError(f"未知扫描器: {scanner_name}, 可选: {list(SCANNERS.keys())}")

    cfg = SCANNERS[scanner_name]
    check_fn = _load_check_fn(scanner_name)

    # 合并默认参数
    params = {**cfg['params'], **kwargs}

    stock_list = get_stock_list(market)

    def check(code, name):
        return check_fn(code, name, **params)

    results, _ = scan_all(stock_list, check, workers=workers,
                          label=cfg['desc'], exclude_st=True)
    return results


def list_scanners():
    """列出所有可用扫描器"""
    print(f"\n{'名称':20s} {'说明':15s} {'默认参数'}")
    print("-" * 70)
    for name, cfg in SCANNERS.items():
        params_str = ", ".join(f"{k}={v}" for k, v in cfg['params'].items())
        print(f"{name:20s} {cfg['desc']:15s} {params_str}")
    print()


def cli():
    """CLI入口"""
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help', 'help'):
        print("fire-earth 扫描器")
        print(f"\n用法: python run.py <scanner> [options]")
        print(f"\n可用扫描器:")
        list_scanners()
        print("示例:")
        print("  python run.py daily-pattern --pattern 101000 --market 688")
        print("  python run.py xichou --period weekly")
        print("  python run.py volume-breakout --max-range-ratio 1.10")
        return

    scanner_name = sys.argv[1]
    if scanner_name not in SCANNERS:
        print(f"❌ 未知扫描器: {scanner_name}")
        list_scanners()
        return

    # 解析剩余参数 (简单key=value格式)
    kwargs = {}
    market = 'all'
    workers = 20
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg.startswith('--'):
            key = arg[2:].replace('-', '_')
            if key == 'market':
                market = sys.argv[i + 1] if i + 1 < len(sys.argv) else 'all'
                i += 2
            elif key == 'workers':
                workers = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 20
                i += 2
            elif i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith('--'):
                val = sys.argv[i + 1]
                # 保持为字符串的参数
                if key in ('pattern', 'period'):
                    pass
                else:
                    # 尝试转数字
                    try:
                        val = int(val)
                    except ValueError:
                        try:
                            val = float(val)
                        except ValueError:
                            pass
                kwargs[key] = val
                i += 2
            else:
                kwargs[key] = True
                i += 1
        else:
            i += 1

    results = scan(scanner_name, market=market, workers=workers, **kwargs)

    if results:
        print(f"\n✅ 共命中 {len(results)} 只")
    else:
        print("\n❌ 无命中")


if __name__ == "__main__":
    cli()
