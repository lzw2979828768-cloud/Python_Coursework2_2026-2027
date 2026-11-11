"""Fixed QR Mask0 and format writing, independent of optional mask selection."""

import numpy as np

from .format_info import build_format_bits
from ..models import EncodingPlan, MaskSelection, MatrixLayout, PayloadType
from ..tracing import TraceCollector


def _format_positions(size: int) -> tuple[tuple[tuple[int, int], ...], ...]:
    """Return both format-copy coordinate sequences, most-significant bit first."""
    around_top_left = (
        tuple((8, col) for col in range(6))
        + ((8, 7), (8, 8), (7, 8))
        + tuple((row, 8) for row in range(5, -1, -1))
    )
    opposite_copy = (
        tuple((row, 8) for row in range(size - 1, size - 8, -1))
        + tuple((8, col) for col in range(size - 8, size))
    )
    return around_top_left, opposite_copy


def apply_fixed_mask_zero(
    layout: MatrixLayout, plan: EncodingPlan, *, trace: TraceCollector | None = None,
) -> MaskSelection:
    """Copy layout, mask only data modules, and write both format copies.

    The formula is (row + col) % 2 == 0. Reserved modules are never flipped;
    only the subsequent format-writing operation changes the 30 format cells.
    Inputs and previous snapshots remain unchanged. Return mask_id=0, a
    read-only final matrix without quiet zone, and an empty score mapping.
    Wrong types raise TypeError; layout/plan inconsistencies raise ValueError.
    """
    if not isinstance(layout, MatrixLayout):
        raise TypeError("layout must be a MatrixLayout")
    if not isinstance(plan, EncodingPlan):
        raise TypeError("plan must be an EncodingPlan")
    if layout.version != plan.version or layout.modules.shape != (plan.matrix_size,) * 2:
        raise ValueError("Layout version and dimensions must match the plan")
    expected_data_modules = 8 * plan.total_codewords + plan.remainder_bits
    if int(np.count_nonzero(~layout.reserved_mask)) != expected_data_modules:
        raise ValueError("Layout data-module count must match the plan")

    size = plan.matrix_size
    copies = _format_positions(size)
    if any(not layout.reserved_mask[row, col] for positions in copies for row, col in positions):
        raise ValueError("Both format-information copies must be reserved")
    if not layout.reserved_mask[size - 8, 8] or layout.modules[size - 8, 8] != 1:
        raise ValueError("The fixed dark module must be reserved and black")

    matrix = layout.modules.copy()
    rows, cols = np.indices(matrix.shape)
    flip = ~layout.reserved_mask & ((rows + cols) % 2 == 0)
    matrix[flip] ^= 1
    if trace is not None:
        trace.record(
            "mask0.applied", "固定 Mask0", "仅翻转非保留区中行号与列号之和为偶数的模块。",
            PayloadType.MATRIX, matrix,
        )

    format_bits = build_format_bits(plan.ecc_level, 0)
    if (not isinstance(format_bits, tuple) or len(format_bits) != 15
            or any(type(bit) is not int or bit not in (0, 1) for bit in format_bits)):
        raise ValueError("Format encoder must return 15 integer bits as a tuple")
    if trace is not None:
        trace.record(
            "mask0.format_bits", "格式信息编码",
            f"已为 {plan.ecc_level}/Mask0 生成含 BCH 和固定异或的 15 位格式信息，高位在前。",
            PayloadType.BITS, format_bits,
        )
    for positions in copies:
        for bit, (row, col) in zip(format_bits, positions):
            matrix[row, col] = bit

    selection = MaskSelection(mask_id=0, final_matrix=matrix, penalty_scores={})
    if trace is not None:
        trace.record(
            "mask0.final_matrix", "格式写入与主体完成",
            "两份格式信息已写入；固定深色模块保持黑色，二维码主体已完成。",
            PayloadType.MATRIX, selection.final_matrix,
        )
    return selection
