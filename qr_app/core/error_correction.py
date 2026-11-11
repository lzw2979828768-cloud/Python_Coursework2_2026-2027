"""Data ECC boundary; format information uses a separate algorithm."""

from ..errors import ErrorCode, QRGenerationError
from ..models import EncodingPlan, FinalCodewords
from ..tracing import TraceCollector


def build_final_codewords(
    data_codewords: bytes, plan: EncodingPlan, *, trace: TraceCollector | None = None,
) -> FinalCodewords:
    """TODO Stage1: reedsolo ECC; return interleaved bytes and remainder bits."""
    raise QRGenerationError(ErrorCode.FEATURE_UNAVAILABLE, "数据纠错与码字交织尚未实现。")
