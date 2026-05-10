"""LLM服务模块 (LangChain 版本)"""

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from typing import Optional
from ..config import get_llm_config, get_settings

# 全局 LLM 实例
_llm_instance: Optional[BaseChatModel] = None


def get_llm() -> BaseChatModel:
    """获取 LangChain LLM 实例（单例模式）"""
    global _llm_instance

    if _llm_instance is None:
        settings = get_settings()
        # 从环境变量读取 LLM 配置
        api_key, base_url, model, timeout = get_llm_config()

        # 验证必要的配置
        if not api_key:
            raise ValueError("LLM_API_KEY 未配置（LLM 必需）")

        # 创建 ChatOpenAI 实例
        _llm_instance = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=settings.agent_temperature,
            max_tokens=2000,
            timeout=timeout,
            max_retries=3
        )

        print(f"[SUCCESS] LangChain LLM 初始化成功")
        print(f"   模型: {model}")
        print(f"   Base URL: {base_url}")

    return _llm_instance


def reset_llm():
    """重置 LLM 实例（用于测试或重新配置）"""
    global _llm_instance
    _llm_instance = None
