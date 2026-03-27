"""
OpenAI API客户端封装模块。
提供与OpenAI API交互的统一接口，支持重试和错误处理。
"""
from typing import Any, Dict, List, Optional

from loguru import logger
from openai import AsyncOpenAI

from app.core.config import settings


class AIClient:
    """OpenAI API客户端，封装所有与大模型的交互"""

    def __init__(self) -> None:
        # 延迟初始化：客户端实例在首次调用时才创建，避免启动阶段的无效连接
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """
        获取或创建OpenAI客户端实例（懒加载单例）。

        Returns:
            AsyncOpenAI: 异步OpenAI客户端实例
        """
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
        return self._client

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        调用聊天补全API。

        Args:
            messages: 消息列表，每条消息包含 role 和 content 两个字段
            model: 模型名称，为空时使用配置文件中的默认模型
            temperature: 温度参数，值越高输出越随机，0.0为确定性输出
            max_tokens: 单次请求最大生成token数

        Returns:
            str: 模型生成的文本内容

        Raises:
            Exception: 当API调用失败时抛出原始异常
        """
        client = self._get_client()
        # 未指定模型时，回退到全局配置的默认模型
        model = model or settings.OPENAI_MODEL

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            logger.info(
                f"AI响应成功，模型: {model}, "
                f"使用tokens: {response.usage.total_tokens}"
            )
            return content
        except Exception as e:
            logger.error(f"AI API调用失败: {e}")
            raise

    async def chat_completion_with_json(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """
        调用聊天补全API，强制要求返回JSON格式。

        通过设置 response_format 为 json_object，引导模型返回合法JSON。
        温度默认设低（0.3），以提高结构化输出的稳定性。

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数（默认0.3，较低以保证输出稳定性）
            max_tokens: 最大生成token数

        Returns:
            str: 模型生成的JSON文本

        Raises:
            Exception: 当API调用失败时抛出原始异常
        """
        client = self._get_client()
        model = model or settings.OPENAI_MODEL

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            logger.info(
                f"AI JSON响应成功，模型: {model}, "
                f"使用tokens: {response.usage.total_tokens}"
            )
            return content
        except Exception as e:
            logger.error(f"AI JSON API调用失败: {e}")
            raise


# 全局AI客户端单例，供各服务模块直接导入使用
ai_client = AIClient()
