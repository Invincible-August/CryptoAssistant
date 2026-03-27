"""
自定义异常模块。
定义系统中使用的所有自定义异常类。
"""
from typing import Any, Optional


class AppException(Exception):
    """
    应用基础异常类。
    所有自定义异常均继承此类，统一异常响应格式。

    Attributes:
        message: 人类可读的错误描述
        code: HTTP状态码
        detail: 附加错误详情（可选）
    """

    def __init__(self, message: str = "系统内部错误", code: int = 500, detail: Any = None):
        self.message = message
        self.code = code
        self.detail = detail
        super().__init__(self.message)


class AuthenticationError(AppException):
    """认证失败异常，如令牌无效或已过期"""

    def __init__(self, message: str = "认证失败，请重新登录"):
        super().__init__(message=message, code=401)


class AuthorizationError(AppException):
    """权限不足异常，用户无权执行目标操作"""

    def __init__(self, message: str = "权限不足，无法执行此操作"):
        super().__init__(message=message, code=403)


class NotFoundError(AppException):
    """
    资源不存在异常。

    Args:
        resource: 资源名称，用于生成友好的错误提示
        message: 自定义错误消息，优先级高于自动生成的消息
    """

    def __init__(self, resource: str = "资源", message: Optional[str] = None):
        msg = message or f"{resource}不存在"
        super().__init__(message=msg, code=404)


class ValidationError(AppException):
    """
    参数校验异常。
    当请求参数不符合预期格式或约束时抛出。

    Args:
        message: 错误描述
        detail: 具体的校验错误信息（如字段级别的错误列表）
    """

    def __init__(self, message: str = "请求参数校验失败", detail: Any = None):
        super().__init__(message=message, code=422, detail=detail)


class ExchangeAPIError(AppException):
    """
    交易所API调用异常。
    当Binance或其他交易所接口调用失败时抛出。

    Args:
        exchange: 交易所名称
        message: 具体错误描述
    """

    def __init__(self, exchange: str = "Binance", message: str = "交易所API调用失败"):
        super().__init__(message=f"{exchange}: {message}", code=502)


class RateLimitError(AppException):
    """请求频率限制异常，触发交易所或系统的速率限制时抛出"""

    def __init__(self, message: str = "请求过于频繁，请稍后再试"):
        super().__init__(message=message, code=429)


class ModuleDisabledError(AppException):
    """
    模块未启用异常。
    当用户访问未在配置中启用的功能模块时抛出。

    Args:
        module_name: 未启用的模块名称
    """

    def __init__(self, module_name: str):
        super().__init__(message=f"模块 {module_name} 未启用", code=403)
