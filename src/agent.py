#!/usr/bin/env python3
"""
OPC AI Agent — CLI 入口（开发与调试用）。
Web 端见根目录 app.py。
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_core import run, SCENARIOS, FX  # noqa: E402

# 兼容旧调用：gpt-4o-mini 等提示已失效，这里仅保留 CLI 说明
USAGE = """
CLI 调试入口。日常使用请跑网页版：python app.py 然后打开 http://localhost:8000

  python src/agent.py --scenario A_listing --brief "速干冲浪冲锋衣, 防水" --market uk
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="OPC AI Agent CLI")
    ap.add_argument("--scenario", default="A_listing", choices=list(SCENARIOS))
    ap.add_argument("--brief", required=True)
    ap.add_argument("--market", default="uk")
    args = ap.parse_args()

    out, cost = run(args.scenario, args.brief, args.market)
    print(out)
    print(
        f"\n--- 单次成本估算: ${cost:.4f} (~¥{cost*FX:.4f}) | "
        f"月 1k 次 ≈ ¥{cost*FX*1000:.0f} ---"
    )


if __name__ == "__main__":
    main()
