# src/research_agent/agents/filter/triage_agent.py
import json
from openai import OpenAI
import os
from dotenv import load_dotenv
from loguru import logger
from src.research_agent.llm.clients import get_env_any
from src.research_agent.llm.kimi import KIMI_BASE_URL, build_kimi_extra_body

load_dotenv()
QWEN_BASE_URL = "https://bobdong.cn/v1"
KIMI_MODEL = "kimi-k2.5"
QWEN_MODEL = "Qwen3.5-Plus"
MIN_STORE_SCORE = 4

DEFAULT_INSTRUCTION = """
你是一个严谨的学术助手。请根据用户的【研究领域画像】，判断给定的论文是否值得深入阅读。
请务必严格筛选，只有当论文明确涉及用户关注的技术或应用场景时才返回 True。泛泛而谈的论文应被过滤。

注意：论文只需要符合用户画像中的任意一条兴趣即可判定为相关。

请以 JSON 格式返回结果，包含两个字段:
- "is_relevant": true 或 false
- "reason": 一句话解释原因（如果相关，说明符合哪条兴趣；如果不相关，说明缺失了什么）。
"""

DEFAULT_PROFILE = """
1. 人工智能在土木工程中的应用 (AI in Civil Engineering)
2. 隧道工程的变形预测、结构健康监测 (Tunnel SHM)
3. 数字孪生技术 (Digital Twin)
"""

class RelevanceFilter:
    def __init__(self, research_interests: str | list[str]):
        self.kimi_client = OpenAI(
            api_key=os.getenv("KIMI_API_KEY"),
            base_url=KIMI_BASE_URL,
        )
        self.qwen_client = OpenAI(
            api_key=get_env_any("BOB_API_KEY", "QWEN_API_KEY"),
            base_url=QWEN_BASE_URL,
        )
        self.kimi_extra_body = build_kimi_extra_body(KIMI_MODEL, KIMI_BASE_URL)
        self.interest_items = self._normalize_research_interests(research_interests)
        self.interests = self._format_interests(self.interest_items)

    @staticmethod
    def _format_interests(fields: list[str]) -> str:
        return "\n".join([f"{i+1}. {field}" for i, field in enumerate(fields)])

    @staticmethod
    def _parse_interests_from_text(interests_text: str) -> list[str]:
        items = []
        for line in interests_text.splitlines():
            text = line.strip()
            if not text:
                continue
            if "." in text and text.split(".", 1)[0].strip().isdigit():
                text = text.split(".", 1)[1].strip()
            if text:
                items.append(text)
        return items

    def _normalize_research_interests(self, research_interests: str | list[str]) -> list[str]:
        """Normalize caller-provided interests without reading global config."""
        if isinstance(research_interests, list):
            items = [str(item).strip() for item in research_interests if str(item).strip()]
        else:
            items = self._parse_interests_from_text(research_interests or "")

        if items:
            return items

        logger.warning("⚠️ No research interests provided, using DEFAULT_PROFILE")
        return self._parse_interests_from_text(DEFAULT_PROFILE)

    def _sanitize_interest_indices(self, raw_indices) -> list[int]:
        if not isinstance(raw_indices, list):
            return []

        valid = []
        max_idx = len(self.interest_items)
        for idx in raw_indices:
            try:
                value = int(idx)
            except (TypeError, ValueError):
                continue
            if 1 <= value <= max_idx and value not in valid:
                valid.append(value)
        return valid

    @staticmethod
    def _compute_relevance_score(matched_count: int, total_interests: int) -> int:
        if matched_count <= 0:
            return 0
        safe_total = max(1, total_interests)
        score = round((matched_count / safe_total) * 10)
        return max(1, min(10, score))

    def _call_model(self, client: OpenAI, model: str, prompt: str, extra_body=None):
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        if extra_body:
            kwargs["extra_body"] = extra_body
        return client.chat.completions.create(**kwargs)

    def _call_relevance_llm(self, prompt: str):
        attempts = [
            ("Kimi", self.kimi_client, KIMI_MODEL, self.kimi_extra_body),
            ("Qwen", self.qwen_client, QWEN_MODEL, None),
        ]

        errors = []
        for provider_name, client, model, extra_body in attempts:
            try:
                logger.info(f"🧠 RelevanceFilter using {provider_name} model: {model}")
                return self._call_model(client, model, prompt, extra_body=extra_body)
            except Exception as e:
                errors.append(f"{provider_name}: {e}")
                logger.warning(f"⚠️ {provider_name} relevance check failed: {e}")

        raise RuntimeError("; ".join(errors)) if errors else RuntimeError("No LLM provider available")


    def check_relevance(self, title: str, abstract: str) -> dict:
        """
        返回 {'is_relevant': bool, 'reason': str, 'relevance_score': int, ...}
        relevance_score 由命中兴趣点数量决定，命中越多评分越高。
        """
        prompt = f"""
        你是一个严谨的学术助手。请判断以下论文与我的研究兴趣有多少项匹配。

        我的研究兴趣（编号列表）:
        {self.interests}

        论文标题: {title}
        论文摘要: {abstract}

        规则：
        1) 仅统计“明确相关”的兴趣点，不要宽泛联想。
        2) 如果没有任何兴趣点匹配，返回空数组。
        3) matched_interest_indices 中的编号必须来自上面的兴趣编号。

        请只返回 JSON，格式如下：
        {{
          "matched_interest_indices": [1, 3],
          "reason": "简短说明命中的兴趣点，以及为何匹配"
        }}
        """

        try:
            response = self._call_relevance_llm(prompt)
            result = json.loads(response.choices[0].message.content)

            matched_indices = self._sanitize_interest_indices(result.get("matched_interest_indices", []))

            # 兼容旧格式输出（防止模型偶发不按新 schema 返回）
            if not matched_indices and result.get("is_relevant") is True:
                matched_indices = [1] if self.interest_items else []

            matched_count = len(matched_indices)
            score = self._compute_relevance_score(matched_count, len(self.interest_items))
            is_relevant = matched_count > 0 and score >= MIN_STORE_SCORE

            reason = str(result.get("reason", "")).strip()
            if not reason:
                if is_relevant:
                    reason = f"匹配到 {matched_count} 个兴趣点"
                else:
                    reason = "与兴趣点无明确匹配"
            if matched_count > 0 and score < MIN_STORE_SCORE:
                reason = f"评分 {score} 低于入库阈值 {MIN_STORE_SCORE}，不进入数据库"

            matched_interests = [self.interest_items[i - 1] for i in matched_indices]

            return {
                "is_relevant": is_relevant,
                "reason": reason,
                "relevance_score": score,
                "matched_interest_count": matched_count,
                "matched_interest_indices": matched_indices,
                "matched_interests": matched_interests,
            }
        except Exception as e:
            logger.error(f"⚠️ 筛选出错: {e}")
            return {
                "is_relevant": None,
                "reason": "Error during LLM check",
                "relevance_score": 0,
                "error": str(e),
            }
