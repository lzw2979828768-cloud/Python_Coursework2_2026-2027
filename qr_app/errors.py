"""Safe errors shared by the core, service and presentation layers."""

from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_OPTION = "INVALID_OPTION"
    MODE_PARAMETER_CONFLICT = "MODE_PARAMETER_CONFLICT"
    FEATURE_UNAVAILABLE = "FEATURE_UNAVAILABLE"
    EMPTY_INPUT = "EMPTY_INPUT"
    UNSUPPORTED_CHARACTER = "UNSUPPORTED_CHARACTER"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    INTERNAL_GENERATION_ERROR = "INTERNAL_GENERATION_ERROR"
    LOG_WRITE_FAILED = "LOG_WRITE_FAILED"
    ARTIFACT_SAVE_FAILED = "ARTIFACT_SAVE_FAILED"
    USAGE_READ_FAILED = "USAGE_READ_FAILED"


class QRGenerationError(Exception):
    """Expected generation failure; details must contain only safe metadata."""

    def __init__(
        self, code: str, message: str, details: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = message
        self.details = MappingProxyType(dict(details or {}))


class QRContractError(TypeError):
    """The caller did not supply a structurally valid request."""

    code = ErrorCode.INVALID_REQUEST

    def __init__(self, message: str = "请求结构或字段类型不符合公共契约。") -> None:
        super().__init__(message)
        self.message = message


class ArtifactSaveError(Exception):
    """Presentation-layer save failure, independent of QR generation."""

    code = ErrorCode.ARTIFACT_SAVE_FAILED

    def __init__(self, message: str = "图像保存失败。") -> None:
        super().__init__(message)
        self.message = message


class UsageReadError(Exception):
    """History could not be read; this does not mean the history is empty."""

    code = ErrorCode.USAGE_READ_FAILED

    def __init__(self, message: str = "使用记录读取失败。") -> None:
        super().__init__(message)
        self.message = message
