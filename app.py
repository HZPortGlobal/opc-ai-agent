#!/usr/bin/env python3
"""
OPC AI Agent — 线上 SaaS（Flask）。
启动：python app.py  →  打开 http://localhost:8000
部署：见 README「部署」一节（Render 免费层）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from agent_core import run, SCENARIOS, FX  # noqa: E402
from flask import Flask, request, jsonify, render_template
import store  # noqa: E402

store.init()

app = Flask(__name__)

# 给前端用的友好标签（A 是主推方向，B/C 作为可选模块保留）
LABELS = {
    "A_listing": "🛒 Listing 生成（标题 / 卖点 / 描述 / 社媒文案）",
    "A_cs": "💬 客服回复草稿（多语言，含风险提示）",
    "B_code": "🔍 代码审查（分级问题 + 安全/性能陷阱）",
    "C_research": "📊 行业研究简报（市场 / 竞品 / 风险）",
}


@app.route("/")
def index():
    return render_template("index.html", scenarios=LABELS)


@app.route("/waitlist")
def waitlist_page():
    return render_template("waitlist.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    scenario = data.get("scenario", "A_listing")
    brief = (data.get("brief") or "").strip()
    market = data.get("market", "uk")
    if not brief:
        return jsonify({"error": "brief 不能为空"}), 400
    try:
        out, cost = run(scenario, brief, market)
    except SystemExit as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # 兜底：密钥缺失 / 网络 / 模型错误都回 500
        return jsonify({"error": f"生成失败：{e}"}), 500
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


@app.route("/api/waitlist", methods=["POST"])
def waitlist():
    d = request.get_json(force=True, silent=True) or {}
    email = (d.get("email") or "").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "邮箱格式不对"}), 400
    added = store.add_wait(email, d.get("source", ""))
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
<div class="card">waitlist 邮箱数：<b>{s['waitlist']}</b> ｜ 反馈条数：<b>{s['feedback']}</b></div>
<div class="card"><h3>各场景使用量</h3><table>{sc_rows}</table></div>
<div class="card"><h3>反馈正负</h3><table>{rating_rows}</table></div>
<div class="card"><h3>愿付 £/月 分布</h3><table>{wtp_rows}</table></div>
<p class="mut">注：当前用 SQLite 存于服务实例，Render 免费层重部署会清空。正式化时换外部数据库。</p>
</body></html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
