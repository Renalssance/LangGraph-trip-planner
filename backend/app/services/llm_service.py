"""LLM服务模块 (LangChain 版本)"""

from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from typing import Any, Optional
from datetime import datetime
import json
import logging
from pathlib import Path
from ..config import get_llm_config, get_settings

logger = logging.getLogger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[2]

# 全局 LLM 实例
_llm_instance: Optional[BaseChatModel] = None


class ProviderReasoningChatOpenAI(ChatOpenAI):
    """ChatOpenAI variant that round-trips provider reasoning_content.

    Some OpenAI-compatible reasoning models require `reasoning_content` from an
    assistant tool-call message to be sent back in the next request. LangChain's
    generic ChatOpenAI intentionally drops provider-specific fields, so preserve
    just this one field for agent tool loops.
    """

    def _create_chat_result(self, response: Any, generation_info: dict | None = None):
        result = super()._create_chat_result(response, generation_info)
        response_dict = response if isinstance(response, dict) else response.model_dump()

        for index, (generation, choice) in enumerate(
            zip(result.generations, response_dict.get("choices", []))
        ):
            raw_message = choice.get("message", {})
            reasoning_content = raw_message.get("reasoning_content")
            if reasoning_content is None and not isinstance(response, dict):
                choices = getattr(response, "choices", [])
                if index < len(choices):
                    reasoning_content = getattr(
                        getattr(choices[index], "message", None),
                        "reasoning_content",
                        None,
                    )
            message = getattr(generation, "message", None)
            if isinstance(message, AIMessage) and reasoning_content is not None:
                message.additional_kwargs["reasoning_content"] = reasoning_content

        return result

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        payload_messages = payload.get("messages")
        if not isinstance(payload_messages, list):
            return payload

        source_messages = self._convert_input(input_).to_messages()
        for source_message, payload_message in zip(source_messages, payload_messages):
            if (
                isinstance(source_message, AIMessage)
                and isinstance(payload_message, dict)
                and "reasoning_content" in source_message.additional_kwargs
            ):
                payload_message["reasoning_content"] = source_message.additional_kwargs[
                    "reasoning_content"
                ]

        return payload


class LLMResponseLogger(BaseCallbackHandler):
    """Write each completed LLM response to a dedicated JSONL file."""

    def __init__(self, max_chars: int = 6000, log_dir: str = "logs/llm"):
        self.max_chars = max_chars
        self.log_dir = self._resolve_log_dir(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        run_id = kwargs.get("run_id", "unknown")
        try:
            for prompt_index, generations in enumerate(response.generations):
                for generation_index, generation in enumerate(generations):
                    message = getattr(generation, "message", None)
                    text = self._extract_generation_text(generation, message)
                    tool_calls = getattr(message, "tool_calls", None) if message else None
                    reasoning_content = None
                    if message:
                        reasoning_content = getattr(message, "additional_kwargs", {}).get(
                            "reasoning_content"
                        )
                    response_metadata = getattr(message, "response_metadata", None) if message else None
                    token_usage = None
                    if response_metadata:
                        token_usage = response_metadata.get("token_usage") or response_metadata.get("usage")

                    self._write_record({
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "run_id": str(run_id),
                        "prompt_index": prompt_index,
                        "generation_index": generation_index,
                        "content": self._truncate(text),
                        "reasoning_content": (
                            self._truncate(reasoning_content) if reasoning_content else None
                        ),
                        "tool_calls": tool_calls,
                        "token_usage": token_usage,
                    })
        except Exception as exc:
            logger.warning("记录 LLM 返回内容失败: %s", exc, exc_info=True)

    def _resolve_log_dir(self, log_dir: str) -> Path:
        path = Path(log_dir).expanduser()
        if path.is_absolute():
            return path
        return BACKEND_ROOT / path

    def _write_record(self, record: dict) -> None:
        log_file = self.log_dir / f"llm_responses_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with log_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def _extract_generation_text(self, generation: Any, message: Any) -> str:
        if message is not None:
            content = getattr(message, "content", "")
            if isinstance(content, str):
                if content:
                    return content
                reasoning_content = getattr(message, "additional_kwargs", {}).get(
                    "reasoning_content"
                )
                if reasoning_content:
                    return str(reasoning_content)
            return json.dumps(content, ensure_ascii=False, default=str)

        text = getattr(generation, "text", "")
        if isinstance(text, str):
            return text
        return json.dumps(text, ensure_ascii=False, default=str)

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_chars:
            return text
        return f"{text[:self.max_chars]}\n...[已截断，完整长度 {len(text)} 字符]"


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

        callbacks = []
        if settings.llm_log_responses:
            callbacks.append(LLMResponseLogger(
                max_chars=settings.llm_log_response_max_chars,
                log_dir=settings.llm_log_dir,
            ))

        llm_kwargs: dict[str, Any] = {}
        thinking_mode = settings.llm_thinking_mode.strip().lower()
        if thinking_mode in {"deepseek-disabled", "thinking-disabled"}:
            llm_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        elif thinking_mode == "qwen-disabled":
            llm_kwargs["extra_body"] = {"enable_thinking": False}
        elif thinking_mode in {"deepseek-enabled", "thinking-enabled"}:
            llm_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        elif thinking_mode == "qwen-enabled":
            llm_kwargs["extra_body"] = {"enable_thinking": True}

        # 创建 ChatOpenAI 实例
        _llm_instance = ProviderReasoningChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=settings.agent_temperature,
            max_tokens=4000,
            timeout=timeout,
            max_retries=3,
            callbacks=callbacks or None,
            **llm_kwargs,
        )

        print(f"[SUCCESS] LangChain LLM 初始化成功")
        print(f"   模型: {model}")
        print(f"   Base URL: {base_url}")
        print(f"   Thinking模式: {settings.llm_thinking_mode}")
        print(f"   LLM响应日志: {'启用，写入文件' if settings.llm_log_responses else '禁用'}")

    return _llm_instance


def reset_llm():
    """重置 LLM 实例（用于测试或重新配置）"""
    global _llm_instance
    _llm_instance = None
