# src/research_agent/agents/filter/triage_agent.py
import json
from openai import OpenAI
import os
from dotenv import load_dotenv
from sqlmodel import Session, select
from src.research_agent.storage.models import engine, SystemConfig
from loguru import logger
import yaml
from pathlib import Path

load_dotenv() # 加载 .env 中的 API KEY

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
    def __init__(self, research_interests: str):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.interests = self._load_research_interests()

    def _load_research_interests(self) -> str:
        """Load research interests from user_config.yaml"""
        config_path = Path(__file__).parent.parent.parent / "config" / "user_config.yaml"
        
        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    if config and "fields" in config:
                        # Convert list to numbered string format
                        fields = config.get("fields", [])
                        if fields:
                            interests = "\n".join([f"{i+1}. {field}" for i, field in enumerate(fields)])
                            logger.info(f"✅ Loaded research interests from config:\n{interests}")
                            return interests
                logger.warning("⚠️ No 'fields' found in user_config.yaml, using DEFAULT_PROFILE")
            else:
                logger.warning(f"⚠️ Config file not found at {config_path}, using DEFAULT_PROFILE")
        except Exception as e:
            logger.warning(f"⚠️ Error loading config: {e}, using DEFAULT_PROFILE")
        
        return DEFAULT_PROFILE


    def check_relevance(self, title: str, abstract: str) -> dict:
        """
        返回 {'is_relevant': bool, 'reason': str}
        """
        prompt = f"""
        你是一个严谨的学术助手。请判断以下论文是否在我的研究兴趣中。
        
        我的研究兴趣包含了: {self.interests}
        
        论文标题: {title}
        论文摘要: {abstract}
        
        请严格筛选。只有当论文明确存在于我广泛的的研究领域，并且是我的研究兴趣之一时才返回 True。
        请注意，我的各个研究兴趣之间的关系是OR，因此只要符合其中一个兴趣即可判定为相关。
        请以 JSON 格式返回结果，包含两个字段:
        - "is_relevant": true 或 false
        - "reason": 一句话解释原因
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini", # 使用轻量级模型以降低成本
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"⚠️ 筛选出错: {e}")
            return {"is_relevant": False, "reason": "Error during LLM check"}