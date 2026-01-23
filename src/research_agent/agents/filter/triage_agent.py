# src/research_agent/agents/filter/triage_agent.py
import json
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv() # 加载 .env 中的 API KEY

class RelevanceFilter:
    def __init__(self, research_interests: str):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.interests = research_interests

    def check_relevance(self, title: str, abstract: str) -> dict:
        """
        返回 {'is_relevant': bool, 'reason': str}
        """
        prompt = f"""
        你是一个严谨的学术助手。请判断以下论文是否与我的研究兴趣高度相关。
        
        我的研究兴趣: {self.interests}
        
        论文标题: {title}
        论文摘要: {abstract}
        
        请严格筛选。只有当论文明确涉及我的研究领域时才返回 True。
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