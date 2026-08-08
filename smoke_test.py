#!/usr/bin/env python3
"""冒烟测试：验证路由、支付/会员端点、额度门控、密钥降级均正常。"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod
from store import create_redeem_code, redeem_code

client = appmod.app.test_client()

results = []


def check(name, fn):
    try:
        ok, info = fn()
        results.append((name, ok, info))
        print(("PASS " if ok else "FAIL ") + name + "  " + info)
    except Exception as e:  # noqa
        results.append((name, False, "EXC: " + str(e)))
        print("FAIL " + name + "  EXC: " + str(e))


# 1. 落地页
def t_landing():
    r = client.get("/landing")
    txt = r.get_data(as_text=True)
    return r.status_code == 200 and ("免费体检" in txt) and ("member" in txt), f"[{r.status_code}]"


check("GET /landing 渲染+会员区", t_landing)


# 2. 配额
def t_quota():
    r = client.post("/api/quota", json={"uid": "u1"})
    d = r.get_json()
    return r.status_code == 200 and d.get("free_limit") == 3, f"[{r.status_code}] {d}"


check("POST /api/quota", t_quota)


# 3. 空 brief
def t_empty():
    r = client.post("/api/check", json={"brief": "", "market": "uk"})
    return r.status_code == 400, f"[{r.status_code}] {r.get_json()}"


check("POST /api/check 空brief→400", t_empty)


# 4. 有效 brief → 密钥降级（不再 500 崩溃，而是 503 预热中）
def t_modeldown():
    r = client.post("/api/check", json={"brief": "Men's wetsuit best 100% safe", "market": "uk"})
    d = r.get_json()
    return r.status_code in (500, 503) and isinstance(d, dict) and "error" in d, f"[{r.status_code}] {d}"


check("POST /api/check 密钥降级→5xx友好", t_modeldown)


# 5. 会员码核销
TEST_CODE = "TEST-SMOKE-0001"
create_redeem_code(TEST_CODE, plan="pro", credits=9999)


def t_redeem_bad():
    r = client.post("/api/redeem", json={"code": "NOPE"})
    return r.status_code == 400, f"[{r.status_code}] {r.get_json()}"


check("POST /api/redeem 无效码→400", t_redeem_bad)


def t_redeem_ok():
    r = client.post("/api/redeem", json={"code": TEST_CODE, "uid": "u1"})
    d = r.get_json()
    return r.status_code == 200 and d.get("ok") is True, f"[{r.status_code}] {d}"


check("POST /api/redeem 有效码→200", t_redeem_ok)


# 6. 会员码体检：跳过免费额度（不应 402）
def t_member_check():
    r = client.post("/api/check", json={"brief": "Men's wetsuit", "market": "uk", "member_code": TEST_CODE})
    d = r.get_json()
    return r.status_code != 402, f"[{r.status_code}] 跳过额度(down={d.get('model_down')})"


check("POST /api/check 会员码跳过额度", t_member_check)


# 7. 支付状态 / 创建
def t_pay_status():
    r = client.get("/api/pay/status")
    d = r.get_json()
    return r.status_code == 200 and "price_cny" in d, f"[{r.status_code}] {d}"


check("GET /api/pay/status", t_pay_status)


def t_pay_create():
    r = client.post("/api/pay/create", json={"channel": "wechat"})
    d = r.get_json()
    return r.status_code == 200 and d.get("status") in ("manual_pending", "created"), f"[{r.status_code}] {d}"


check("POST /api/pay/create 微信(未配置→manual_pending)", t_pay_create)


# 8. 看板
def t_stats():
    r = client.get("/stats")
    txt = r.get_data(as_text=True)
    return r.status_code == 200 and "会员数" in txt, f"[{r.status_code}]"


check("GET /stats 含会员数", t_stats)

failed = [n for n, ok, _ in results if not ok]
print("\n==== 结果:", "全部通过" if not failed else f"{len(failed)} 项失败: {failed}")
sys.exit(1 if failed else 0)
