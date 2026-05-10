"""配置管理模块"""

import os
from pathlib import Path
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载环境变量
# 显式加载 backend/.env,避免从仓库根目录启动时找不到配置
backend_env = Path(__file__).resolve().parent.parent / ".env"
if backend_env.exists():
    load_dotenv(backend_env, override=False)
else:
    load_dotenv()

# 然后尝试加载HelloAgents的.env(如果存在)
helloagents_env = Path(__file__).parent.parent.parent.parent / "HelloAgents" / ".env"
if helloagents_env.exists():
    load_dotenv(helloagents_env, override=False)  # 不覆盖已有的环境变量


class Settings(BaseSettings):
    """应用配置"""

    # 应用基本配置
    app_name: str = "多agent的智能旅行助手"
    app_version: str = "1.5.0"
    debug: bool = False

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS配置 - 使用字符串,在代码中分割
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    # 高德地图API配置
    amap_api_key: str = ""

    # Unsplash API配置
    unsplash_access_key: str = ""
    unsplash_secret_key: str = ""

    # LLM配置 (优先读取 LLM_* 环境变量,兼容旧 OPENAI_* 变量)
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model_id: str = "qwen3.6-plus-2026-04-02"
    llm_timeout: float = 60.0

    # LangChain 配置
    langchain_tracing: bool = False  # 是否启用 LangSmith 追踪
    langchain_endpoint: str = "https://api.smith.langchain.com"
    langchain_api_key: str = ""
    langchain_project: str = "trip-planner"

    # 智能体配置
    agent_max_iterations: int = 2
    agent_temperature: float = 0.7
    agent_timeout: float = 90.0

    # 日志配置
    log_level: str = "INFO"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        """Allow environment names such as release/prod for DEBUG."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "off", "no"}:
                return False
            if normalized in {"debug", "dev", "development", "true", "1", "on", "yes"}:
                return True
        return value

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # 忽略额外的环境变量

    def get_cors_origins_list(self) -> List[str]:
        """获取CORS origins列表"""
        return [origin.strip() for origin in self.cors_origins.split(',')]


# 创建全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings


def get_llm_config():
    """获取LLM配置,兼容历史 OPENAI_* 环境变量。"""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or settings.llm_api_key
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or settings.llm_base_url
    model = os.getenv("LLM_MODEL_ID") or os.getenv("OPENAI_MODEL") or settings.llm_model_id
    timeout = os.getenv("LLM_TIMEOUT") or settings.llm_timeout
    return api_key, base_url, model, float(timeout)


# 验证必要的配置
def validate_config():
    """验证配置是否完整"""
    errors = []
    warnings = []

    if not settings.amap_api_key:
        errors.append("AMAP_API_KEY未配置")

    # LangChain 使用 OpenAI 兼容接口,配置名统一为 LLM_*
    llm_api_key, _, _, _ = get_llm_config()
    if not llm_api_key:
        errors.append("LLM_API_KEY 未配置（LLM 必需）")

    # LangChain 配置检查
    if settings.langchain_tracing and not settings.langchain_api_key:
        warnings.append("启用了 LangSmith 追踪但未配置 LANGCHAIN_API_KEY")

    if errors:
        error_msg = "配置错误:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)

    if warnings:
        print("\n⚠️  配置警告:")
        for w in warnings:
            print(f"  - {w}")

    return True


# 打印配置信息(用于调试)
def print_config():
    """打印当前配置(隐藏敏感信息)"""
    print(f"应用名称: {settings.app_name}")
    print(f"版本: {settings.app_version}")
    print(f"服务器: {settings.host}:{settings.port}")
    print(f"高德地图API Key: {'已配置' if settings.amap_api_key else '未配置'}")

    # 检查LLM配置
    llm_api_key, llm_base_url, llm_model_id, llm_timeout = get_llm_config()

    print(f"LLM API Key: {'已配置' if llm_api_key else '未配置'}")
    print(f"LLM Base URL: {llm_base_url}")
    print(f"LLM Model: {llm_model_id}")
    print(f"LLM 超时: {llm_timeout}秒")
    print(f"LangChain 追踪: {'启用' if settings.langchain_tracing else '禁用'}")
    print(f"智能体最大迭代次数: {settings.agent_max_iterations}")
    print(f"智能体温度: {settings.agent_temperature}")
    print(f"智能体超时: {settings.agent_timeout}秒")
    print(f"日志级别: {settings.log_level}")
