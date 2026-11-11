"""Unmasked matrix and reserved-region construction boundary."""

from ..errors import ErrorCode, QRGenerationError
from ..models import EncodingPlan, MatrixLayout
from ..tracing import TraceCollector


def build_matrix(
    bitstream: tuple[int, ...], plan: EncodingPlan, *, trace: TraceCollector | None = None,
) -> MatrixLayout:
    """TODO Stage1: function patterns, reservations and zigzag data placement."""
    raise QRGenerationError(ErrorCode.FEATURE_UNAVAILABLE, "功能图案与数据落位尚未实现。")
