# OPC AI Agent — 线上 SaaS

OPC（一人公司）模式下的 AI Agents 产品：用户选任务、填 brief，后端调用大模型
（默认 DeepSeek，OpenAI 兼容可换）实时生成 —— Listing / 客服 / 代码审查 / 行业研究。
单次成本 ≈ ¥0.005–0.01，毛利 99%+，是「月入三万 / 半年百万」的数学前提。

## 本地运行
```bash
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
cp .env.example .env        # 填入 OPENAI_API_KEY
python app.py               # 打开 http://localhost:8000
```

## 部署（公开上线）
见 `DEPLOY.md` —— 支持 **Hugging Face Spaces（免信用卡）** 与 **Render** 两种免费路径，
密钥一律放进平台 Secrets，绝不进仓库（`.env` 已被 `.gitignore` 屏蔽）。

## 当前状态
- [x] 4 场景全部真实跑通（A_listing / A_cs / B_code / C_research）
- [x] Web SaaS 上线本地（Flask + DeepSeek）
- [x] 部署包就绪（Procfile / render.yaml / Dockerfile / DEPLOY.md）
- [ ] 推到公开 URL、获取首个真实付费信号
- [ ] 第 3 周：数据筛方向，不过线场景零情感砍掉
