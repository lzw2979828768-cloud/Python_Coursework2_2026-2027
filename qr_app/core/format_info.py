"""QR format BCH coding, independent of Reed-Solomon data ECC.

Return 15 bits most-significant first. QR format information uses BCH(15,5)
with generator 0x537 and a final XOR mask of 0x5412.
Reference: https://www.thonky.com/qr-code-tutorial/format-version-information
"""

from ..models import ECCLevel

_ECC_FORMAT_VALUES = {"L": 0b01, "M": 0b00, "Q": 0b11, "H": 0b10}
_BCH_GENERATOR = 0x537
_FORMAT_XOR_MASK = 0x5412


def build_format_bits(ecc_level: ECCLevel, mask_id: int) -> tuple[int, ...]:
    """Return the actual ECC/mask format codeword as 15 integer bits, MSB first.

    Accept ECCLevel or its exact L/M/Q/H string value. Wrong argument types
    raise TypeError; unsupported levels or mask IDs raise ValueError.
    Bool is not a valid integer mask ID. This calculation has no side effects.
    """
    if not isinstance(ecc_level, str):
        raise TypeError("ecc_level must be an ECCLevel or L/M/Q/H string")
    if ecc_level not in _ECC_FORMAT_VALUES:
        raise ValueError("ecc_level must be L, M, Q or H")
    if type(mask_id) is not int:
        raise TypeError("mask_id must be an integer, not bool")
    if mask_id not in range(8):
        raise ValueError("mask_id must be between 0 and 7")

    data = (_ECC_FORMAT_VALUES[ecc_level] << 3) | mask_id
    remainder = data << 10
    while remainder.bit_length() >= _BCH_GENERATOR.bit_length():
        shift = remainder.bit_length() - _BCH_GENERATOR.bit_length()
        remainder ^= _BCH_GENERATOR << shift
    codeword = ((data << 10) | remainder) ^ _FORMAT_XOR_MASK
    return tuple((codeword >> shift) & 1 for shift in range(14, -1, -1))
