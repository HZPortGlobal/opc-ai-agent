#!/usr/bin/env python3
"""
OPC AI Agent — 线上 SaaS（Flask）。
启动：python app.py  →  打开 http://localhost:8000
部署：见 README「部署」一节（Render 免费层）。

定位：做英国/欧洲市场的中国出海卖家「AI 上架合规官」。
"""
import os
import secrets
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from agent_core import run, SCENARIOS, FX  # noqa: E402
from flask import Flask, request, jsonify, render_template
import store  # noqa: E402
import pay as paymod  # noqa: E402

store.init()

FREE_DAILY_LIMIT = int(os.environ.get("FREE_DAILY_LIMIT", "3"))
MEMBER_PRICE_CNY = int(os.environ.get("MEMBER_PRICE_CNY", "199"))
# 支付平台巡检必需的经营主体信息（填在部署环境变量里，不写死在代码中）
SITE_ENTITY = os.environ.get("SITE_ENTITY", "")
SITE_EMAIL = os.environ.get("SITE_EMAIL", "")
SITE_PHONE = os.environ.get("SITE_PHONE", "")


def _site_ctx():
    """页脚经营信息上下文（供支付平台合规巡检查验）。"""
    return {
        "site_entity": SITE_ENTITY,
        "site_email": SITE_EMAIL,
        "site_phone": SITE_PHONE,
        "price_cny": MEMBER_PRICE_CNY,
        "free_limit": FREE_DAILY_LIMIT,
    }
# 微信/支付宝原生支付（商户配置齐备后自动开通扫码支付；未配置走会员码兜底）
WECHAT_CFG = bool(
    os.environ.get("WECHAT_MCH_ID")
    and os.environ.get("WECHAT_PRIVATE_KEY")
    and os.environ.get("WECHAT_APIV3_KEY")
)
ALIPAY_CFG = bool(
    os.environ.get("ALIPAY_APP_ID")
    and os.environ.get("ALIPAY_APP_PRIVATE_KEY")
    and os.environ.get("ALIPAY_PUBLIC_KEY")
)

app = Flask(__name__)

# 给前端用的友好标签（A_audit 为主推，生成/客服/研究为附属）
LABELS = {
    "A_audit": "🛡️ 上架合规体检（粘贴现成 Listing，查 GPSR/宣称/用语风险）【主推】",
    "A_listing": "🛒 Listing 生成（标题/卖点/描述/社媒，生成即合规）",
    "A_cs": "💬 客服回复草稿（多语言，含风险提示）",
    "C_research": "📊 行业研究简报（市场/竞品/风险）",
}


@app.route("/")
def index():
    # 根路径直接展示新版合规体检落地页（含会员区/支付）；旧工具页保留在 /tool
    return render_template("landing.html", **_site_ctx())


@app.route("/tool")
def tool():
    return render_template("index.html", scenarios=LABELS)


@app.route("/waitlist")
def waitlist_page():
    return render_template("waitlist.html")


@app.route("/landing")
def landing():
    return render_template("landing.html", **_site_ctx())


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()


def _gen_err(e, scenario, market, uid):
    """生成异常统一转友好响应：鉴权失败→503 预热中；其余→500。"""
    store.log_usage(scenario, market, False, uid)
    msg = str(e)
    if "401" in msg or "Authentication" in msg or "auth" in msg.lower():
        return (
            jsonify(
                {
                    "error": "AI 模型密钥无效或已失效，服务预热中，暂不能生成。请稍后再试或联系管理员。",
                    "model_down": True,
                }
            ),
            503,
        )
    return jsonify({"error": f"生成失败：{e}"}), 500


@app.route("/api/quota", methods=["POST"])
def quota():
    ip = _client_ip()
    day = time.strftime("%Y-%m-%d")
    return jsonify(
        {"free_used": store.get_free_count(ip, day), "free_limit": FREE_DAILY_LIMIT}
    )


@app.route("/api/check", methods=["POST"])
def check():
    """免费合规体检（匿名 IP 每日额度 / 会员码无限），超额引导付费。"""
    data = request.get_json(force=True, silent=True) or {}
    brief = (data.get("brief") or "").strip()
    market = data.get("market", "uk")
    member_code = (data.get("member_code") or "").strip()
    if not brief:
        return jsonify({"error": "请粘贴需体检的 Listing 内容"}), 400

    ip = _client_ip()
    day = time.strftime("%Y-%m-%d")

    # 会员码：跳过免费额度，无限体检
    if member_code and store.is_member(member_code):
        try:
            out, cost = run("A_audit", brief, market)
            store.log_usage("A_audit", market, True, member_code)
        except SystemExit as e:
            store.log_usage("A_audit", market, False, member_code)
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return _gen_err(e, "A_audit", market, member_code)
        return jsonify(
            {
                "output": out,
                "cost_cny": round(cost * FX, 5),
                "member": True,
                "free_used": 0,
                "free_limit": FREE_DAILY_LIMIT,
            }
        )

    # 免费额度路径
    used = store.get_free_count(ip, day)
    if used >= FREE_DAILY_LIMIT:
        return (
            jsonify(
                {
                    "paywall": True,
                    "free_used": used,
                    "free_limit": FREE_DAILY_LIMIT,
                    "error": f"今日免费体检次数已用完（{FREE_DAILY_LIMIT} 次/天），开通会员可继续使用。",
                }
            ),
            402,
        )
    try:
        out, cost = run("A_audit", brief, market)
        store.log_usage("A_audit", market, True, "")
        store.inc_free_count(ip, day)
    except SystemExit as e:
        store.log_usage("A_audit", market, False, "")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _gen_err(e, "A_audit", market, "")
    return jsonify(
        {
            "output": out,
            "cost_cny": round(cost * FX, 5),
            "free_used": used + 1,
            "free_limit": FREE_DAILY_LIMIT,
        }
    )


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    scenario = data.get("scenario", "A_audit")
    brief = (data.get("brief") or "").strip()
    market = data.get("market", "uk")
    uid = (data.get("uid") or "").strip()
    if not brief:
        return jsonify({"error": "brief 不能为空"}), 400
    try:
        out, cost = run(scenario, brief, market)
        store.log_usage(scenario, market, True, uid)
    except SystemExit as e:
        store.log_usage(scenario, market, False, uid)
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # 兜底：密钥缺失 / 网络 / 模型错误
        return _gen_err(e, scenario, market, uid)
    return jsonify(
        {
            "output": out,
            "cost_usd": round(cost, 5),
            "cost_cny": round(cost * FX, 5),
        }
    )


@app.route("/api/feedback", methods=["POST"])
def feedback():
    d = request.get_json(force=True, silent=True) or {}
    scenario = d.get("scenario", "")
    market = d.get("market", "")
    rating = d.get("rating", "")
    comment = (d.get("comment") or "").strip()[:500]
    try:
        wtp = int(d.get("wtp") or 0)
    except (TypeError, ValueError):
        wtp = 0
    if rating not in ("up", "down"):
        return jsonify({"error": "rating 必须是 up/down"}), 400
    store.add_feedback(scenario, market, rating, comment, wtp)
    return jsonify({"ok": True})


@app.route("/api/redeem", methods=["POST"])
def redeem():
    """核销会员码 → 解锁无限体检。"""
    d = request.get_json(force=True, silent=True) or {}
    code = (d.get("code") or "").strip()
    if not code:
        return jsonify({"error": "请输入会员码"}), 400
    m = store.redeem_code(code, d.get("uid", ""))
    if not m:
        return jsonify({"error": "会员码无效或已使用"}), 400
    return jsonify({"ok": True, "plan": m["plan"], "credits": m["credits"]})


@app.route("/api/pay/status")
def pay_status():
    """前端据此决定展示扫码支付还是体验码兜底。"""
    return jsonify(
        {
            "wechat": WECHAT_CFG,
            "alipay": ALIPAY_CFG,
            "price_cny": MEMBER_PRICE_CNY,
        }
    )


@app.route("/api/pay/create", methods=["POST"])
def pay_create():
    """创建支付单。商户号已配置 → 微信 Native / 支付宝当面付下单返回二维码；否则 manual_pending。"""
    d = request.get_json(force=True, silent=True) or {}
    channel = (d.get("channel") or "wechat").lower()
    if channel not in ("wechat", "alipay"):
        return jsonify({"error": "channel 仅支持 wechat/alipay"}), 400

    # 未配置商户 → 会员码兜底
    configured = WECHAT_CFG if channel == "wechat" else ALIPAY_CFG
    if not configured:
        store.log_payment(channel, MEMBER_PRICE_CNY, "manual_pending")
        return (
            jsonify(
                {
                    "status": "manual_pending",
                    "channel": channel,
                    "message": "商户号待配置，暂走人工/体验码；商户号就绪后将自动开通扫码支付并回调发货。",
                }
            ),
            200,
        )

    # 已配置 → 真实下单
    order_no = f"{'WX' if channel == 'wechat' else 'ALI'}{int(time.time() * 1000)}{secrets.token_hex(2).upper()}"
    try:
        if channel == "wechat":
            pay_url = paymod.wechat_native(order_no, MEMBER_PRICE_CNY)
            ptype = "native"
        else:
            pay_url = paymod.alipay_precreate(order_no, MEMBER_PRICE_CNY)
            ptype = "precreate"
    except Exception as e:
        store.log_payment(channel, MEMBER_PRICE_CNY, "error", meta=f"{order_no}|{str(e)[:200]}")
        return jsonify({"status": "error", "message": f"下单失败：{e}"}), 502

    store.log_payment(channel, MEMBER_PRICE_CNY, "created", meta=order_no)
    return (
        jsonify(
            {
                "status": "created",
                "channel": channel,
                "pay_url": pay_url,
                "type": ptype,
                "order_no": order_no,
                "message": "请扫码支付，支付成功后会员自动开通（无需填码）。",
            }
        ),
        200,
    )


@app.route("/api/pay/notify/wechat", methods=["POST"])
def pay_notify_wechat():
    """微信支付回调：验签解密 → 成功则自动 mint 会员码发货。"""
    raw = request.get_data(as_text=True)
    try:
        res = paymod.wechat_verify_notify(request.headers, raw)
    except Exception as e:
        return jsonify({"code": "FAIL", "message": str(e)}), 400
    if res.get("trade_state") == "SUCCESS" and res.get("out_trade_no"):
        paymod.issue_member_code("wechat", res["out_trade_no"], MEMBER_PRICE_CNY)
        return jsonify({"code": "SUCCESS", "message": "成功"})
    return jsonify({"code": "FAIL", "message": "trade not success"}), 400


@app.route("/api/pay/notify/alipay", methods=["POST"])
def pay_notify_alipay():
    """支付宝异步通知：验签 → 成功则自动 mint 会员码发货。"""
    form = request.form.to_dict()
    try:
        paymod.alipay_verify_notify(form)
    except Exception:
        return "fail"
    if form.get("trade_status") in ("TRADE_SUCCESS", "TRADE_FINISHED") and form.get("out_trade_no"):
        paymod.issue_member_code("alipay", form["out_trade_no"], MEMBER_PRICE_CNY)
        return "success"
    return "fail"


@app.route("/api/waitlist", methods=["POST"])
def waitlist():
    d = request.get_json(force=True, silent=True) or {}
    email = (d.get("email") or "").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "邮箱格式不对"}), 400
    added = store.add_wait(email, d.get("source", ""), d.get("uid", ""))
    return jsonify({"ok": True, "added": added})


@app.route("/stats")
def stats():
    s = store.stats()
    sc_rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in s["by_scenario"].items()
    ) or "<tr><td colspan='2'>暂无</td></tr>"
    wtp_rows = "".join(
        f"<tr><td>£{w}</td><td>{n}</td></tr>" for w, n in s["wtp"]
    ) or "<tr><td colspan='2'>暂无</td></tr>"
    rating_rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in s["by_rating"].items()
    ) or "<tr><td colspan='2'>暂无</td></tr>"
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>数据看板</title><style>
body{{font-family:-apple-system,Segoe UI,sans-serif;background:#0f1115;color:#e8ecf2;margin:0;padding:32px}}
h1{{font-size:20px}} .card{{background:#171a21;border:1px solid #262b36;border-radius:12px;padding:16px;margin:12px 0}}
table{{width:100%;border-collapse:collapse;font-size:14px}} td{{padding:8px;border-bottom:1px solid #262b36}}
.mut{{color:#8b93a3;font-size:12px}}
</style></head><body>
<h1>数据看板（MVP · 本地实例存储）</h1>
<div class="card">waitlist 邮箱数：<b>{s['waitlist']}</b> ｜ 反馈条数：<b>{s['feedback']}</b> ｜ 会员数：<b>{s['members']}</b> ｜ 独立用户：<b>{s['distinct_users']}</b> ｜ 近7日活跃：<b>{s['users_7d']}</b></div>
<div class="card">生成总次数：<b>{s['gen_total']}</b> ｜ 成功率：<b>{s['success_rate']}%</b></div>
<div class="card"><h3>各场景使用量</h3><table>{sc_rows}</table></div>
<div class="card"><h3>反馈正负</h3><table>{rating_rows}</table></div>
<div class="card"><h3>愿付 £/月 分布</h3><table>{wtp_rows}</table></div>
<p class="mut">注：当前用 SQLite 存于服务实例，Render 免费层重部署会清空。正式化时换外部数据库。</p>
</body></html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
