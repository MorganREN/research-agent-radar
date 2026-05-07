"""
快速测试不同大模型 API 接口是否可用
运行: python test.py
"""

import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from src.research_agent.llm.kimi import (
    build_kimi_extra_body,
    extract_message_content,
    extract_message_reasoning,
)

load_dotenv()

# ── 配置要测试的模型 ──────────────────────────────────────────────
# 每项格式: (显示名称, model_id, api_key 环境变量, base_url 或 None)
# base_url 为 None 时使用 OpenAI 官方端点
MODELS_TO_TEST = [
    # OpenAI 官方模型
    # ("GPT-4o-mini",  "gpt-4o-mini",  "OPENAI_API_KEY", None),
    # ("GPT-5-mini",   "gpt-5-mini",   "OPENAI_API_KEY", None),
    # ("GPT-5.1",      "gpt-5.1",      "OPENAI_API_KEY", None),

    # ── 如需测试其他供应商，取消注释并填入对应环境变量 ──
    # ("Claude-sonnet", "claude-sonnet-4-20250514", "ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/"),
    ("DeepSeek-V3.2",   "DeepSeek-V3.2",           "DEEPSEEK_API_KEY",  "https://api.deepseek.com"),
    # ("Qwen-Plus",     "qwen-plus",               "QWEN_API_KEY",      "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    # ("kimi-k2.5",       "kimi-k2.5",               "BOB_API_KEY",      "https://bobdong.cn/v1"),
    ("GLM-5.1",         "GLM-5.1",                 "BOB_API_KEY",        "https://bobdong.cn/v1"),
    ("Qwen3.5-Plus",     "Qwen3.5-Plus",             "BOB_API_KEY",       "https://bobdong.cn/v1"),
    # ("Gemini-2.5-Flash", "gemini-2.5-flash",     "GEMINI_API_KEY",    "https://generativelanguage.googleapis.com/v1beta/openai/"),
]

TEST_PROMPT = (
    "Write a haiku about the beauty of nature in spring. "
    "以中文写一个关于春天自然美的俳句。"
    "只输出最终答案，不要输出推理过程。"
)
def test_model(name: str, model: str, api_key_env: str, base_url: str | None) -> dict:
    """测试单个模型，返回结果字典"""
    api_key = os.getenv(api_key_env)
    if not api_key:
        return {"name": name, "status": "SKIP", "detail": f"环境变量 {api_key_env} 未设置", "latency": 0}

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)

    t0 = time.time()
    try:
        request_kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": TEST_PROMPT}],
            "max_tokens": 2048,
            "timeout": 30,
        }
        extra_body = build_kimi_extra_body(model, base_url)
        if extra_body:
            request_kwargs["extra_body"] = extra_body

        resp = client.chat.completions.create(
            **request_kwargs,
        )
        latency = time.time() - t0
        message = resp.choices[0].message
        content = extract_message_content(message)
        if not content:
            finish_reason = getattr(resp.choices[0], "finish_reason", "unknown")
            reasoning = extract_message_reasoning(message)
            if reasoning:
                content = (
                    f"[no final content] finish_reason={finish_reason}; "
                    f"reasoning_len={len(reasoning)}"
                )
            else:
                content = f"[empty response] finish_reason={finish_reason}"
        return {"name": name, "status": "PASS", "detail": content, "latency": latency}
    except Exception as e:
        latency = time.time() - t0
        return {"name": name, "status": "FAIL", "detail": str(e)[:120], "latency": latency}


def main():
    print("\n" + "=" * 64)
    print("  🔍  大模型 API 接口连通性测试")
    print("=" * 64 + "\n")

    results = []
    for name, model, key_env, base_url in MODELS_TO_TEST:
        print(f"  Testing {name:<20s} ({model}) ...", end=" ", flush=True)
        r = test_model(name, model, key_env, base_url)
        results.append(r)

        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️ "}[r["status"]]
        latency_str = f"{r['latency']:.2f}s" if r["latency"] else ""
        print(f"{icon} {r['status']}  {latency_str}  {r['detail']}")

    # ── 汇总 ──
    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    print("\n" + "-" * 64)
    print(f"  汇总: {passed} 通过 / {failed} 失败 / {skipped} 跳过  (共 {len(results)} 个模型)")
    print("-" * 64 + "\n")


if __name__ == "__main__":
    main()
