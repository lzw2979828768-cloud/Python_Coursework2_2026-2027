"""QR data Reed-Solomon encoding, block interleaving and remainder bits.

QR uses GF(256), primitive polynomial 0x11D, generator 2 and roots beginning
at alpha**0. Format-information BCH encoding belongs to format_info.py.
References: https://www.thonky.com/qr-code-tutorial/error-correction-coding
and https://www.thonky.com/qr-code-tutorial/structure-final-message
"""

from reedsolo import RSCodec

from ..models import BlockGroup, EncodingPlan, FinalCodewords, PayloadType
from ..tracing import TraceCollector

_RS_FIELD_SIZE = 255


def _split_data_blocks(
    data_codewords: bytes, groups: tuple[BlockGroup, ...],
) -> tuple[bytes, ...]:
    """Consume contiguous data blocks in group order, without changing input."""
    blocks = []
    offset = 0
    for group in groups:
        for _ in range(group.block_count):
            end = offset + group.data_codewords_per_block
            block = data_codewords[offset:end]
            if len(block) != group.data_codewords_per_block:
                raise ValueError("Data is shorter than the block-group specification")
            blocks.append(block)
            offset = end
    if offset != len(data_codewords):
        raise ValueError("Data is longer than the block-group specification")
    return tuple(blocks)


def _interleave_blocks(blocks: tuple[bytes, ...]) -> bytes:
    """Read each column of the blocks, skipping exhausted shorter blocks."""
    return bytes(
        block[column]
        for column in range(max((len(block) for block in blocks), default=0))
        for block in blocks
        if column < len(block)
    )


def build_final_codewords(
    data_codewords: bytes, plan: EncodingPlan, *, trace: TraceCollector | None = None,
) -> FinalCodewords:
    """Encode each data block, interleave data/ECC, then append remainder bits.

    Input must contain exactly plan.data_codewords padded data bytes.
    TypeError denotes wrong argument types; ValueError denotes inconsistent
    lengths, oversized RS blocks or an invalid encoder result. The service
    converts unexpected computation errors into its safe generation failure.
    Completed trace stages remain available if a later operation fails.
    No input mutation, UI access or file writes occur.
    """
    if not isinstance(data_codewords, bytes):
        raise TypeError("data_codewords must be bytes")
    if not isinstance(plan, EncodingPlan):
        raise TypeError("plan must be an EncodingPlan")
    if len(data_codewords) != plan.data_codewords:
        raise ValueError("Data codeword count must match plan.data_codewords")
    if any(group.data_codewords_per_block + plan.ecc_codewords_per_block > _RS_FIELD_SIZE
           for group in plan.block_groups):
        # RSCodec otherwise silently chunks a long block and adds extra ECC.
        raise ValueError("Each QR RS block must fit within 255 codewords")

    data_blocks = _split_data_blocks(data_codewords, plan.block_groups)
    if trace is not None:
        for block_id, block in enumerate(data_blocks, 1):
            trace.record(
                f"ecc.block_{block_id}.data", f"数据分块 {block_id}",
                f"按编码计划取得 {len(block)} 个数据码字。",
                PayloadType.CODEWORDS, block,
            )

    codec = RSCodec(
        nsym=plan.ecc_codewords_per_block, nsize=_RS_FIELD_SIZE,
        fcr=0, prim=0x11D, generator=2, c_exp=8,
    )
    ecc_blocks = []
    for block_id, block in enumerate(data_blocks, 1):
        encoded_block = bytes(codec.encode(block))
        if (len(encoded_block) != len(block) + plan.ecc_codewords_per_block
                or encoded_block[:len(block)] != block):
            raise ValueError("RS encoder output disagrees with the data block and plan")
        parity = encoded_block[len(block):]
        ecc_blocks.append(parity)
        if trace is not None:
            trace.record(
                f"ecc.block_{block_id}.parity", f"纠错分块 {block_id}",
                f"在 GF(256) 上生成 {len(parity)} 个 Reed-Solomon 纠错码字。",
                PayloadType.CODEWORDS, parity,
            )

    interleaved_data = _interleave_blocks(data_blocks)
    if trace is not None:
        trace.record(
            "ecc.interleaved_data", "数据码字交织", "逐列读取各数据块，跳过已耗尽的短块。",
            PayloadType.CODEWORDS, interleaved_data,
        )
    interleaved_ecc = _interleave_blocks(tuple(ecc_blocks))
    if trace is not None:
        trace.record(
            "ecc.interleaved_parity", "纠错码字交织", "逐列读取各纠错块。",
            PayloadType.CODEWORDS, interleaved_ecc,
        )
    interleaved_codewords = interleaved_data + interleaved_ecc
    if len(interleaved_codewords) != plan.total_codewords:
        raise ValueError("Final codeword count disagrees with the plan")
    if trace is not None:
        trace.record(
            "ecc.final_codewords", "最终码字", "交织后的数据码字在前，纠错码字在后。",
            PayloadType.CODEWORDS, interleaved_codewords,
        )

    remainder_bits = (0,) * plan.remainder_bits
    if trace is not None:
        trace.record(
            "ecc.remainder_bits", "版本余数位",
            f"码字序列之后追加 {plan.remainder_bits} 个零；它们不参与 RS 编码。",
            PayloadType.BITS, remainder_bits,
        )
    bitstream = tuple(
        (codeword >> shift) & 1
        for codeword in interleaved_codewords
        for shift in range(7, -1, -1)
    ) + remainder_bits
    final = FinalCodewords(interleaved_codewords, bitstream)
    if trace is not None:
        trace.record(
            "ecc.bitstream", "最终位流", f"已生成含余数位的 {len(bitstream)} 位位流。",
            PayloadType.BITS, final.bitstream,
        )
    return final
