# 部署到公开 URL（2 分钟上线）

两种免费路径，任选其一。**密钥只在平台 Secrets 里填，不要提交进仓库。**

---

## 路径 A：Hugging Face Spaces（推荐，免信用卡）

1. 登录 https://huggingface.co （用 GitHub 账号即可）
2. 右上角 **New** → **Space** → 填名字（如 `opc-ai-agent`），**SDK 选 Docker**，
   Visibility 选 **Public**
3. 创建后进入 Space，左侧 **Settings → Secrets** 添加：
   - `OPENAI_API_KEY` = 你的 DeepSeek key（sk-...）
   - `OPENAI_BASE_URL` = `https://api.deepseek.com/v1`
   - `OPENAI_MODEL` = `deepseek-chat`
4. 把本仓库文件上传（拖拽即可，包含 Dockerfile + README 的 Space 配置头）：
   - `app.py` / `src/agent_core.py` / `templates/index.html` / `requirements.txt` / `Dockerfile`
   - 仓库根 `README.md` 必须带 Space 配置头（已在仓库内，照抄即可）
5. 等待 build 完成，Space 给你的 `*.hf.space` 就是公开 URL，可直接发给用户收钱。

> Space 配置头（README.md 顶部）：
> ```yaml
> ---
> title: OPC AI Agent
> emoji: 🤖
> colorFrom: blue
> colorTo: indigo
> sdk: docker
> app_port: 7860
> ---
> ```

---

## 路径 B：Render（标准 Web 服务）

1. 登录 https://render.com → **New** → **Web Service** → 连 GitHub 仓库
   （先把本仓库推到你的 GitHub：`git push`）
2. 配置：
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`
   - 选 **Free** 计划
3. **Environment** 里加变量：
   - `OPENAI_BASE_URL` = `https://api.deepseek.com/v1`
   - `OPENAI_MODEL` = `deepseek-chat`
   - `OPENAI_API_KEY` = 你的 key（点 "Secret" 隐藏）
4. Deploy 完成后拿到 `*.onrender.com` 公开 URL。

---

## 上线后第一件事（获取真实付费信号）

按张一鸣打法：产品能跑不等于有人付钱。上线当天就做：
1. 找 1–2 个 UK 小卖家 / 独立开发者 **免费试用一周**，看是否愿意付月费
2. 把试用反馈当成第 3 周「数据筛方向」的输入，不过线场景零情感砍掉
3. 跑通的场景锁死成可订阅产品形态，才是那一百万的前提（不是接定制外包）

> ⚠️ 安全：聊天里贴过的 DeepSeek key 已视为暴露，正式上线前请去
> platform.deepseek.com 吊销并重发一个，只放进平台 Secrets。
