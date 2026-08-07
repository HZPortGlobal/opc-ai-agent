#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键部署 OPC AI Agent 到 Hugging Face Spaces。
在你的电脑（能上网）上运行：
    python deploy_hf.py
按提示粘贴 Hugging Face token（huggingface.co/settings/tokens 生成，勾选 write 权限）。

你的 DeepSeek key 会从本地 .env 自动读取并设为 Space Secret，
绝不会出现在聊天记录或代码仓库里。脚本只用 Python 标准库，无需 pip 安装。
"""
import os
import sys
import json
import shutil
import argparse
import subprocess
import urllib.request
import urllib.error
import getpass

# ---------- 配置（一般不用改） ----------
SPACE_NAME = "opc-ai-agent"
HF_API = "https://huggingface.co/api"
ROOT = os.path.dirname(os.path.abspath(__file__))

FILES = [
    "app.py",
    "requirements.txt",
    "Dockerfile",
    "src/agent_core.py",
    "src/agent.py",
    "templates/index.html",
]

SPACE_README = """---
title: OPC AI Agent
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# OPC AI Agent
选任务 → 填 brief → 实时生成 Listing / 客服 / 代码审查 / 行业研究。
"""


def api(method, path, token, data=None):
    url = HF_API + path
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode("utf-8")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def read_local_ds_key():
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("OPENAI_API_KEY") and "=" in line:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def main():
    parser = argparse.ArgumentParser(description="一键部署 OPC AI Agent 到 HF Spaces")
    parser.add_argument("--token", help="Hugging Face token（可改用环境变量 HF_TOKEN）")
    args = parser.parse_args()

    token = (args.token or os.environ.get("HF_TOKEN") or "").strip()
    if not token:
        token = getpass.getpass("粘贴 Hugging Face token: ").strip()
    if not token:
        sys.exit("未提供 token，已退出。")

    ds_key = read_local_ds_key()
    if not ds_key:
        ds_key = getpass.getpass("本地 .env 未找到 DeepSeek key，请粘贴: ").strip()
    if not ds_key:
        sys.exit("未提供 DeepSeek key，已退出。")

    print("→ 创建 Space ...")
    try:
        info = api("POST", "/spaces", token, {
            "name": SPACE_NAME,
            "sdk": "docker",
            "storage": "durable",
            "private": False,
            "hardware": "cpu-basic",
        })
    except urllib.error.HTTPError as e:
        sys.exit(f"创建 Space 失败 ({e.code})：{e.read().decode('utf-8', 'ignore')}")
    namespace = info.get("id")  # 形如 username/opc-ai-agent
    if not namespace:
        sys.exit("创建失败，响应: " + json.dumps(info))
    print("→ Space 已创建:", namespace)

    clone_url = f"https://hf:{token}@huggingface.co/spaces/{namespace}"
    work = os.path.join(ROOT, "_hf_deploy")
    if os.path.exists(work):
        shutil.rmtree(work)
    subprocess.run(["git", "clone", clone_url, work], check=True)

    for f in FILES:
        src = os.path.join(ROOT, f)
        dst = os.path.join(work, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    with open(os.path.join(work, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(SPACE_README)

    subprocess.run(["git", "-C", work, "add", "-A"], check=True)
    subprocess.run(["git", "-C", work, "commit", "-q", "-m", "deploy opc-ai-agent"], check=True)
    subprocess.run(["git", "-C", work, "push"], check=True)

    # 设置密钥 & 环境变量（失败也不阻断，可稍后在 Space Settings 手动加）
    for key, val, secret in [
        ("OPENAI_API_KEY", ds_key, True),
        ("OPENAI_BASE_URL", "https://api.deepseek.com/v1", False),
        ("OPENAI_MODEL", "deepseek-chat", False),
    ]:
        endpoint = "/secrets" if secret else "/env"
        try:
            api("POST", f"/spaces/{namespace}{endpoint}", token,
                {"key": key, "value": val, "secret": secret})
            print(f"→ 已设置 {'Secret' if secret else 'Env'}: {key}")
        except Exception as e:  # noqa
            print(f"  ! 设置 {key} 失败（可稍后在 Space Settings 手动添加）：{e}")

    print("\n✅ 部署完成！公开 URL：")
    print(f"   https://huggingface.co/spaces/{namespace}")
    print("   （首次 build 约 1–2 分钟，完成后即可把链接发给用户付费使用）")


if __name__ == "__main__":
    main()
