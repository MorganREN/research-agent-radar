from openai import OpenAI
from dotenv import load_dotenv
from loguru import logger
import os

load_dotenv()

class PromptAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_prompt(self, fields: list) -> str:
        '''
        使用用户的研究领域生成专业的生成论文分析的提示语
        '''
        fields_str = "\n".join([f"- {field}" for field in fields])
        generation_prompt = f"""
You are an expert in creating professional academic analysis prompts.

Based on the following research interests, create a comprehensive and professional prompt template that can be used to analyze academic papers. The user is a PhD student focusing on this fields.

**Research Fields of Interest:**
{fields_str}

Please generate a professional prompt template that:
1. Clearly defines the analysis objectives
2. Fully consider that the interests are from different areas and try to be generic
3. Specifies what aspects of the paper should be evaluated
4. Requests structured output in Markdown
5. Emphasises relevance checking against the research fields
6. Asks for key takeaways and potential applications

The prompt should be practical, detailed, and ready to be used with academic papers.

Format your response as a clear, standalone prompt that can be directly used. Except for the prompt, do not reply with any other words.
"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-5-mini",
                messages=[{"role": "user", "content": generation_prompt}],
            )
            prompt_template = response.choices[0].message.content
            # add one line to make sure the output is in markdown format
            prompt_template = prompt_template + "\n\nPlease provide your analysis in Markdown format."
            logger.info("✅ Analysis prompt template generated successfully")
            return prompt_template
        except Exception as e:
            logger.error(f"Error generating prompt template: {e}")
            return ""