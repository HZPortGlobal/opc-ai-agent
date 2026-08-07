# 上线 Render（有代理时 · 2 分钟）

代码已在 GitHub：`https://github.com/HZPortGlobal/opc-ai-agent`
本机有代理即可走通 GitHub 登录（OAuth 跳转不再被墙）。

---

## 第 0 步：重发 DeepSeek key（上线前必做）

聊天里贴过的两个 `sk-...` 已暴露。先去 https://platform.deepseek.com → API keys →
**删掉旧的，新建一个**，复制新 `sk-...`。下面只在 Render 里填这个新的。

## 第 1 步：开代理 + 打开 render.com

确认浏览器走了代理（能正常打开 https://render.com 且不被重置）。

## 第 2 步：用 GitHub 登录 Render

- 点 **Sign Up** / **Log In** → **Continue with GitHub**
- 跳到 GitHub 授权页 → 点 **Authorize render**（允许它读你的仓库）
- 如果列表里看不到 `opc-ai-agent`，点 **Configure** / **Authorize** 把仓库权限放开

## 第 3 步：新建 Web Service

- 登录后右上 **New** → **Web Service**
- **Connect a repository** → 选 GitHub → 找到 `HZPortGlobal/opc-ai-agent` → **Connect**

## 第 4 步：配置（基本不用改）

- Name：`opc-ai-agent`
- Region：**Singapore**（离 UK 近，海外用户访问快）或 Oregon
- Branch：`master`
- Runtime：**Docker**（会自动读仓库里的 `Dockerfile`，无需填 Build/Start 命令）

## 第 5 步：填环境变量（关键）

展开 **Advanced → Environment Variables**，加一条：
- 名称：`OPENAI_API_KEY`
- 值：你**新重发的** DeepSeek key（`sk-...`）
- 右侧点 **Secret** 隐藏

> `OPENAI_BASE_URL` / `OPENAI_MODEL` **不用填**——引擎 `src/agent_core.py` 已默认 DeepSeek。

## 第 6 步：Deploy

点 **Create Web Service**（或 **Deploy**）→ 等 1–2 分钟 build。
状态变绿 **Live** 后，点生成的 `https://opc-ai-agent.onrender.com` 即可访问。

---

## 上线后须知

- **免费层冷启动**：首次/闲置后访问会慢几秒~十几秒（免费层 15 分钟无访问会休眠，下次唤醒），
  属正常，不是挂了。
- **海外访问反而快**：Render 服务器在境外，UK 卖家打开比国内云还顺畅——这是用 Render 的最大好处。
- **真实付费信号**（第 1 周必做）：找 1–2 个 UK 小卖家免费试用一周，
  看是否愿为「自动出 listing + 接客服」付月费；不过线场景零情感砍掉。

> ⚠️ 安全：密钥只放 Render 的 Environment（Secret），不要提交进仓库（`.env` 已被 gitignore）。
