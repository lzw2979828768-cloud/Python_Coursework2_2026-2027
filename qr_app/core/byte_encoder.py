"""Strict text boundary and the shared Byte-mode encoding interface."""

from ..errors import ErrorCode, QRGenerationError
from ..models import EncodedData, EncodingPlan
from ..tracing import TraceCollector


def encode_text(text: str) -> bytes:
    """Encode ISO-8859-1 strictly without trimming or replacing characters."""
    if not isinstance(text, str):
        raise TypeError("encode_text requires str")
    try:
        return text.encode("iso-8859-1", errors="strict")
    except UnicodeEncodeError as error:
        raise QRGenerationError(
            ErrorCode.UNSUPPORTED_CHARACTER, "输入包含 ISO-8859-1 不支持的字符。",
            {"character_index": error.start, "encoding": "iso-8859-1"},
        ) from None


def encode_data(
    data_bytes: bytes, plan: EncodingPlan, *, trace: TraceCollector | None = None,
) -> EncodedData:
    """TODO Stage1: mode/count/data bits, terminator, alignment and pad bytes.

    Read bytes, not text; record completed calculations in trace. No I/O.
    """
    raise QRGenerationError(ErrorCode.FEATURE_UNAVAILABLE, "Byte 模式数据码字编码尚未实现。")
