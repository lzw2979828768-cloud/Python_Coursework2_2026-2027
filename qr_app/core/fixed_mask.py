"""Baseline Mask0 boundary; must not depend on the mask-selection extension."""

from ..errors import ErrorCode, QRGenerationError
from ..models import EncodingPlan, MaskSelection, MatrixLayout
from ..tracing import TraceCollector


def apply_fixed_mask_zero(
    layout: MatrixLayout, plan: EncodingPlan, *, trace: TraceCollector | None = None,
) -> MaskSelection:
    """TODO Stage1: copy layout, mask only data modules, write format info.

    Return mask_id=0 and empty penalty_scores; never change the input layout.
    """
    raise QRGenerationError(ErrorCode.FEATURE_UNAVAILABLE, "固定 Mask0 与格式信息写入尚未实现。")
