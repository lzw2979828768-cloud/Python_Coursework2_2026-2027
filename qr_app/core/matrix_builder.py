"""Unmasked V1/V2 layouts with QR function regions and zigzag data placement.

The two format-information copies are reserved and left white; fixed_mask
writes the actual format bits later. Matrices exclude the quiet zone.
Reference: https://www.thonky.com/qr-code-tutorial/module-placement-matrix
"""

from collections.abc import Iterator

import numpy as np

from ..models import EncodingPlan, MatrixLayout, PayloadType
from ..tracing import TraceCollector

_FINDER_PATTERN = (
    (1, 1, 1, 1, 1, 1, 1),
    (1, 0, 0, 0, 0, 0, 1),
    (1, 0, 1, 1, 1, 0, 1),
    (1, 0, 1, 1, 1, 0, 1),
    (1, 0, 1, 1, 1, 0, 1),
    (1, 0, 0, 0, 0, 0, 1),
    (1, 1, 1, 1, 1, 1, 1),
)
_ALIGNMENT_PATTERN = (
    (1, 1, 1, 1, 1),
    (1, 0, 0, 0, 1),
    (1, 0, 1, 0, 1),
    (1, 0, 0, 0, 1),
    (1, 1, 1, 1, 1),
)


def _place_finder(
    modules: np.ndarray, reserved: np.ndarray, top: int, left: int,
) -> None:
    """Place a finder plus its one-module white separator, clipped to the grid."""
    size = modules.shape[0]
    rows = slice(max(0, top - 1), min(size, top + 8))
    cols = slice(max(0, left - 1), min(size, left + 8))
    modules[rows, cols] = 0
    reserved[rows, cols] = True
    modules[top:top + 7, left:left + 7] = _FINDER_PATTERN


def _reserve_format_and_dark(modules: np.ndarray, reserved: np.ndarray) -> None:
    size = modules.shape[0]
    # Skip the two timing cells (6, 8) and (8, 6) around the upper-left finder.
    first_copy = {(row, 8) for row in range(9) if row != 6}
    first_copy |= {(8, col) for col in range(8) if col != 6}
    second_copy = {(8, col) for col in range(size - 8, size)}
    second_copy |= {(row, 8) for row in range(size - 7, size)}
    for row, col in first_copy | second_copy:
        modules[row, col] = 0
        reserved[row, col] = True
    modules[size - 8, 8] = 1
    reserved[size - 8, 8] = True


def _data_positions(reserved: np.ndarray) -> Iterator[tuple[int, int]]:
    """Visit unreserved cells from bottom-right in alternating two-column bands."""
    size = reserved.shape[0]
    right = size - 1
    upward = True
    while right > 0:
        if right == 6:
            right -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for col in (right, right - 1):
                if not reserved[row, col]:
                    yield row, col
        upward = not upward
        right -= 2


def build_matrix(
    bitstream: tuple[int, ...], plan: EncodingPlan, *, trace: TraceCollector | None = None,
) -> MatrixLayout:
    """Place all supplied bits into an unmasked V1/V2 layout.

    Consume the ECC stage's bitstream, including version remainder bits.
    TypeError denotes wrong container/plan types. ValueError denotes non-bits,
    inconsistent lengths or a plan that disagrees with the grid's capacity.
    Input is not changed; the returned arrays and recorded snapshots own
    independent read-only buffers. No UI, external generator or I/O is used.
    """
    if not isinstance(plan, EncodingPlan):
        raise TypeError("plan must be an EncodingPlan")
    if not isinstance(bitstream, tuple):
        raise TypeError("bitstream must be a tuple of integer bits")
    expected_bits = 8 * plan.total_codewords + plan.remainder_bits
    if len(bitstream) != expected_bits:
        raise ValueError("Bitstream length must match the plan, including remainder bits")
    if any(type(bit) is not int or bit not in (0, 1) for bit in bitstream):
        raise ValueError("bitstream must contain integer 0/1 values")

    size = plan.matrix_size
    modules = np.zeros((size, size), dtype=np.uint8)
    reserved = np.zeros((size, size), dtype=bool)
    for top, left in ((0, 0), (0, size - 7), (size - 7, 0)):
        _place_finder(modules, reserved, top, left)
    if trace is not None:
        trace.record(
            "matrix.finder_patterns", "定位与分隔图案", "放置三个定位图案及白色分隔区。",
            PayloadType.MATRIX, modules,
        )

    if plan.version == 2:
        # V2 has centres [6, 18]; only (18, 18) does not overlap a finder.
        modules[16:21, 16:21] = _ALIGNMENT_PATTERN
        reserved[16:21, 16:21] = True
    if trace is not None:
        trace.record(
            "matrix.alignment_patterns", "对齐图案",
            "V1 无对齐图案。" if plan.version == 1 else "V2 在 (18, 18) 放置一个对齐图案。",
            PayloadType.MATRIX, modules,
        )

    for coordinate in range(8, size - 8):
        value = int(coordinate % 2 == 0)
        modules[6, coordinate] = value
        modules[coordinate, 6] = value
        reserved[6, coordinate] = True
        reserved[coordinate, 6] = True
    if trace is not None:
        trace.record(
            "matrix.timing_patterns", "时序图案", "沿第 6 行与第 6 列放置交替时序模块。",
            PayloadType.MATRIX, modules,
        )

    _reserve_format_and_dark(modules, reserved)
    if trace is not None:
        trace.record(
            "matrix.function_regions", "功能区完成",
            "固定深色模块已放置；两份格式信息共 30 个位置已预留为白色。",
            PayloadType.MATRIX, modules,
        )
        trace.record(
            "matrix.reserved_mask", "保留区标记", "True 表示数据落位和掩码必须跳过的模块。",
            PayloadType.MATRIX, reserved,
        )

    positions = tuple(_data_positions(reserved))
    if len(positions) != expected_bits:
        raise ValueError("Encoding plan bit count disagrees with the grid's data-module capacity")
    for bit, (row, col) in zip(bitstream, positions):
        modules[row, col] = bit
    layout = MatrixLayout(modules=modules, reserved_mask=reserved, version=plan.version)
    if trace is not None:
        trace.record(
            "matrix.data_placed", "数据落位完成",
            f"已将全部 {len(bitstream)} 位放入非保留区；当前为未掩码布局。",
            PayloadType.MATRIX, layout.modules,
        )
    return layout
