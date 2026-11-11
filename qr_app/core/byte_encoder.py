"""Strict ISO-8859-1 and single-segment QR Byte-mode data encoding.

The framing follows the QR Byte-mode mode/count/data, terminator, alignment
and pad-codeword sequence described by Thonky's Data Encoding tutorial:
https://www.thonky.com/qr-code-tutorial/data-encoding
ECC codewords and version remainder bits belong to later stages.
"""

from ..errors import ErrorCode, QRGenerationError
from ..models import EncodedData, EncodingPlan, PayloadType
from ..tracing import TraceCollector

_BYTE_MODE_BITS = (0, 1, 0, 0)
_PAD_CODEWORDS = (0xEC, 0x11)


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


def _integer_bits(value: int, width: int) -> tuple[int, ...]:
    """Return a fixed-width integer field, most-significant bit first."""
    return tuple((value >> shift) & 1 for shift in range(width - 1, -1, -1))


def encode_data(
    data_bytes: bytes, plan: EncodingPlan, *, trace: TraceCollector | None = None,
) -> EncodedData:
    """Frame one Byte segment and pad to plan.data_codewords bytes.

    Input is already encoded bytes; this function never reinterprets text,
    changes the plan, performs I/O or modifies its inputs. Oversized data
    raises QRGenerationError(CAPACITY_EXCEEDED); wrong argument types raise
    TypeError. Completed stages are recorded into the optional request trace.

    Empty bytes are valid at this calculation boundary. The service rejects
    empty user input before calling it, as required by the application rules.
    """
    if not isinstance(data_bytes, bytes):
        raise TypeError("encode_data requires bytes; use encode_text for str")
    if not isinstance(plan, EncodingPlan):
        raise TypeError("plan must be an EncodingPlan")

    byte_length = len(data_bytes)
    capacity_bytes = min(plan.capacity_bytes, (1 << plan.character_count_bits) - 1)
    if byte_length > capacity_bytes:
        raise QRGenerationError(
            ErrorCode.CAPACITY_EXCEEDED, "输入字节数超过所选编码计划的容量。",
            {"byte_length": byte_length, "capacity_bytes": capacity_bytes},
        )
    capacity_bits = 8 * plan.data_codewords

    bits = list(_BYTE_MODE_BITS)
    if trace is not None:
        trace.record(
            "data.mode_indicator", "模式标识", "Byte 模式使用 0100。",
            PayloadType.BITS, _BYTE_MODE_BITS,
        )

    count_bits = _integer_bits(byte_length, plan.character_count_bits)
    bits.extend(count_bits)
    if trace is not None:
        trace.record(
            "data.character_count", "字节长度字段",
            f"将 {byte_length} 字节写入 {plan.character_count_bits} 位长度字段。",
            PayloadType.BITS, count_bits,
        )

    payload_bits = tuple(bit for byte in data_bytes for bit in _integer_bits(byte, 8))
    bits.extend(payload_bits)
    if trace is not None:
        trace.record(
            "data.payload", "数据位", "每个输入字节按高位在前展开为 8 位。",
            PayloadType.BITS, payload_bits,
        )

    # The terminator is bounded by the remaining data capacity.
    terminator_bits = (0,) * min(4, capacity_bits - len(bits))
    bits.extend(terminator_bits)
    if trace is not None:
        trace.record(
            "data.terminator", "终止位", f"追加 {len(terminator_bits)} 个零终止位。",
            PayloadType.BITS, terminator_bits,
        )

    alignment_bits = (0,) * ((-len(bits)) % 8)
    bits.extend(alignment_bits)
    if trace is not None:
        trace.record(
            "data.byte_alignment", "字节对齐",
            f"追加 {len(alignment_bits)} 个零，使位流长度为 8 的倍数。",
            PayloadType.BITS, alignment_bits,
        )

    codewords = bytearray()
    for offset in range(0, len(bits), 8):
        codeword = 0
        for bit in bits[offset:offset + 8]:
            codeword = (codeword << 1) | bit
        codewords.append(codeword)

    padding = bytes(
        _PAD_CODEWORDS[index % 2]
        for index in range(plan.data_codewords - len(codewords))
    )
    codewords.extend(padding)
    if trace is not None:
        trace.record(
            "data.pad_codewords", "填充码字",
            f"从 0xEC 开始交替追加 0xEC / 0x11，共 {len(padding)} 个码字。",
            PayloadType.CODEWORDS, padding,
        )

    encoded = EncodedData(byte_length=byte_length, data_codewords=bytes(codewords))
    if trace is not None:
        trace.record(
            "data.data_codewords", "数据码字完成",
            f"已生成 {len(encoded.data_codewords)} 个数据码字，尚未加入纠错码字。",
            PayloadType.CODEWORDS, encoded.data_codewords,
        )
    return encoded
