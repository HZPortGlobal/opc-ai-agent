#!/usr/bin/env python3
"""
批量生成会员码（体验 / 发售用）。
会员码即「许可证」：用户在前端输入即可解锁无限体检，无需注册登录（避免跟人打交道）。

用法：
    python gen_codes.py            # 默认生成 5 个，前缀 PRO
    python gen_codes.py 20 PRO     # 生成 20 个
    python gen_codes.py 10 VIP     # 前缀 VIP

商户号就绪后，支付回调会自动 mint 会员码并下发，无需手工生成。
"""
import os
import sys
import secrets

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402

store.init()

n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
prefix = sys.argv[2] if len(sys.argv) > 2 else "PRO"


def gen():
    return f"{prefix}-{secrets.token_hex(3).upper()}-{secrets.token_hex(3).upper()}"


codes = []
seen = set()
while len(codes) < n:
    c = gen()
    if c in seen:
        continue
    seen.add(c)
    store.create_redeem_code(c, plan="pro", credits=9999)
    codes.append(c)

print("已生成会员码（pro 套餐，无限体检）：")
for c in codes:
    print("  " + c)
