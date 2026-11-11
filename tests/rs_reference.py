"""Independent test-only QR finite-field reference; does not import reedsolo.

Carryless multiplication with reduction by x^8+x^4+x^3+x^2+1 and direct
polynomial division avoid sharing the production library's log tables.
"""


def gf_multiply(left: int, right: int) -> int:
    product = 0
    for _ in range(8):
        if right & 1:
            product ^= left
        right >>= 1
        left <<= 1
        if left & 0x100:
            left ^= 0x11D
    return product


def parity_from_long_division(data: bytes, count: int) -> bytes:
    generator = [1]
    root = 1
    for _ in range(count):
        multiplied = [0] * (len(generator) + 1)
        for index, coefficient in enumerate(generator):
            multiplied[index] ^= coefficient
            multiplied[index + 1] ^= gf_multiply(coefficient, root)
        generator = multiplied
        root = gf_multiply(root, 2)
    work = list(data) + [0] * count
    for offset in range(len(data)):
        factor = work[offset]
        for index, coefficient in enumerate(generator):
            work[offset + index] ^= gf_multiply(factor, coefficient)
    return bytes(work[-count:])


def syndromes(codewords: bytes, count: int) -> tuple[int, ...]:
    values = []
    root = 1
    for _ in range(count):
        value = 0
        for coefficient in codewords:
            value = gf_multiply(value, root) ^ coefficient
        values.append(value)
        root = gf_multiply(root, 2)
    return tuple(values)
