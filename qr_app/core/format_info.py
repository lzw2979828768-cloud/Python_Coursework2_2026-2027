"""Format information boundary, independent of Reed-Solomon data ECC."""

from ..errors import ErrorCode, QRGenerationError
from ..models import ECCLevel


def build_format_bits(ecc_level: ECCLevel, mask_id: int) -> tuple[int, ...]:
    """TODO Stage1: return 15 format bits including BCH and required XOR."""
    raise QRGenerationError(ErrorCode.FEATURE_UNAVAILABLE, "格式信息编码尚未实现。")
