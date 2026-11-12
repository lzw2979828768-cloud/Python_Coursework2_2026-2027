"""English desktop messages without changing shared service results or CLI text."""

from ..errors import ErrorCode
from ..models import LogState


_GENERATION_ERRORS = {
    ErrorCode.EMPTY_INPUT: "Enter a message or URL before generating a QR code.",
    ErrorCode.UNSUPPORTED_CHARACTER: "Some characters are not supported. Use ISO-8859-1 text.",
    ErrorCode.CAPACITY_EXCEEDED: "Text exceeds the QR capacity. Shorten it and try again.",
    ErrorCode.INVALID_REQUEST: "The request is invalid. Please try again.",
    ErrorCode.INVALID_OPTION: "The selected QR settings are not supported.",
    ErrorCode.MODE_PARAMETER_CONFLICT: "Baseline mode requires Version 1, Level L and Mask 0.",
    ErrorCode.FEATURE_UNAVAILABLE: "This feature is not available in the current application.",
    ErrorCode.INTERNAL_GENERATION_ERROR: "Could not generate the QR code. Please try again.",
}

_WARNINGS = {
    "输入仅含空白，扫码软件显示可能不明显。":
        "The input contains only whitespace. Some scanners may not display it clearly.",
    "使用记录保存失败，统计可能未包含本次请求。":
        "Usage log could not be written. Statistics may not include this request.",
}


def generation_error_text(result):
    message = _GENERATION_ERRORS.get(result.error_code)
    if message is None:
        return "Could not complete this request. Please try again."
    return f"{result.error_code}: {message}"


def generation_warning_texts(result):
    warnings = list(dict.fromkeys(
        _WARNINGS.get(message, "Additional generation warning. Check the content before sharing.")
        for message in result.warnings
    ))
    # Logging diagnostics are internal and may use a different language.
    if result.logging_status.state == LogState.FAILED and not any(
            message.startswith("Usage log could not be written") for message in warnings):
        warnings.append("Usage log could not be written. Statistics may not include this request.")
    return warnings


PNG_SAVE_ERROR = ("Could not save the PNG. Choose an existing folder and a .png filename, "
                  "then check file access and write permissions.")
