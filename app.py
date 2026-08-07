#!/usr/bin/env python3
"""
OPC AI Agent — 线上 SaaS（Flask）。
启动：python app.py  →  打开 http://localhost:8000
部署：见 README「部署」一节（Hugging Face Spaces / Render 免费层）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from agent_core import run, SCENARIOS, FX  # noqa: E402

from flask import Flask, request, jsonify, render_template

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
