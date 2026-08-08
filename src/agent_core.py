#!/usr/bin/env python3
"""
OPC AI Agent — 核心引擎（CLI 与 Web 共用）。
只负责：读 .env → 调 LLM → 返回 (输出文本, USD 成本)。
不关心入口是命令行还是网页。

定位：做英国/欧洲市场的中国出海卖家「AI 上架合规官」。
"""
import os

# .env 固定在项目根目录（与 src/ 同级），无论从哪启动都能找到
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_env_file(path: str = None) -> None:
    """极简 .env 读取，避免额外依赖；已存在的环境变量优先（不覆盖）。"""
    if path is None:
        path = os.path.join(_ROOT, ".env")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                os.environ.setdefault(k, v)
    except FileNotFoundError:
        pass


_load_env_file()

# 粗略成本模型（USD/1k tokens），按你用的模型改。
# 默认值对应 DeepSeek deepseek-chat（输入≈¥0.004/1k、输出≈¥0.016/1k，FX 7.2）。
# 实测：单次约 $0.0009（≈¥0.007），月 1k 次 ≈ ¥7，远低于 ¥2000 预算。
PRICE_PER_1K_IN = 0.0006
PRICE_PER_1K_OUT = 0.0022
FX = 7.2  # USD->CNY 近似

PROMPTS = {
    # 主功能 1：生成即合规的 Listing
    "listing": (
        "你是英国/欧盟市场资深 DTC 运动户外品牌文案，专注冲浪、潜水、户外水上运动品类。基于商品 brief，产出：\n"
        "1) 英文标题（≤80 字符，含核心关键词，如 wetsuit / drysuit / rash guard / fins）\n"
        "2) 5 个英文卖点 bullet（简洁、合规、不夸大；突出材质、氯丁橡胶厚度、适用水温等真实参数）\n"
        "3) 一段 150 词内的英文产品描述\n"
        "4) 一句适合 UK 社媒的中文转发文案\n"
        "UK/EU 合规要求（必须遵循）：材质与性能宣称真实可证；避免绝对化用语（如 'best' 'unbreakable' '100% safe' 'No.1'）；"
        "涉及潜水/安全装备需提示遵循 GPSR 通用产品安全条例的标签与警示要求；美式用词改为英式"
        "（pants→trousers, sneakers→trainers, sweater→jumper, fall→autumn, color→colour, zipper→zip）。\n"
        "只输出结构化结果，不要解释。"
    ),
    # 主功能 2（主推）：粘贴现成 Listing，输出合规体检报告
    "listing_audit": (
        "你是英国/欧盟市场资深合规审核 agent，专注运动户外、冲浪、潜水、水上运动品类。\n"
        "用户会粘贴一段已写好的 Listing（标题 + 卖点 + 描述）。请逐条审查其 UK/EU 上架合规性，输出结构化「合规体检报告」：\n"
        "1) GPSR（通用产品安全条例）风险：是否缺失欧盟责任人/警示/标签类信息的提示；涉及儿童或安全用品时是否有必要警示。\n"
        "2) CE / PPE 风险：若商品属个人防护装备（头盔、护具、某些浮具等），是否标注 CE 与类别（Cat I/II/III）。\n"
        "3) 绝对化/夸大宣称：列出如 best / unbreakable / 100% safe / No.1 / 治愈 等高风险词，并给出改写建议。\n"
        "4) UK vs US 用语：标出美式误用（pants→trousers, sneakers→trainers, sweater→jumper, fall→autumn, color→colour, zipper→zip），给出英式写法。\n"
        "5) 参数与尺码：氯丁橡胶厚度（mm）、适用水温、尺寸表、重量/材质是否清晰真实；缺失则提示补充。\n"
        "6) 总体风险评级：高 / 中 / 低，并给一句结论。\n"
        "每条发现给出：位置（标题/卖点/描述）、风险点、严重程度、修改建议。\n"
        "最后一段免责声明：本结果仅为 AI 风险提示，不构成法律或合规保证，正式上架请以官方要求为准。\n"
        "只输出结构化报告，不要寒暄。"
    ),
    # 附属：客服回复草稿
    "cs_reply": (
        "你是 UK 户外 DTC 品牌的客服 agent。基于客户消息，产出：\n"
        "1) 英文礼貌回复草稿（≤120 词）\n"
        "2) 需要人工确认的风险点（如有）\n"
        "语气专业、克制、不承诺超出政策的范围。"
    ),
    # 附属：行业研究简报（作内容获客）
    "research": (
        "你是行业研究 agent，专注跨境 DTC 与运动户外/水上运动市场。基于给定主题，产出结构化简报：\n"
        "1) 一句话核心结论\n"
        "2) 3-5 个关键事实/数据（标注是否需进一步核实）\n"
        "3) 主要玩家/竞品格局\n"
        "4) 风险与不确定性\n"
        "5) 值得深挖的 2 个问题\n"
        "只输出结构化结果，不要解释过程。"
    ),
}

# 对外暴露的场景（已砍掉代码审查，避免稀释卖家定位）
SCENARIOS = {
    "A_audit": "listing_audit",
    "A_listing": "listing",
    "A_cs": "cs_reply",
    "C_research": "research",
}


def run(scenario_key: str, brief: str, market: str = "uk") -> tuple[str, float]:
    if scenario_key not in SCENARIOS:
        raise SystemExit(f"未知场景 {scenario_key}，可选: {list(SCENARIOS)}")
    if "OPENAI_API_KEY" not in os.environ:
        raise SystemExit("缺环境变量 OPENAI_API_KEY（检查 .env）")
    sys_p = PROMPTS[SCENARIOS[scenario_key]]
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
    )
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "deepseek-chat"),
        messages=[
            {"role": "system", "content": sys_p},
            {"role": "user", "content": f"Market: {market}\nBrief:\n{brief}"},
        ],
        temperature=0.4,
    )
    out = resp.choices[0].message.content or ""
    u = resp.usage
    cost_usd = (u.prompt_tokens / 1000) * PRICE_PER_1K_IN + (
        u.completion_tokens / 1000
    ) * PRICE_PER_1K_OUT
    return out, cost_usd
