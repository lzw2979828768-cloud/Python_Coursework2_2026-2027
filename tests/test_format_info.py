"""Format BCH checks against all 32 published QR format strings."""

import json
from pathlib import Path
import unittest

import numpy as np

from qr_app.core.format_info import build_format_bits
from qr_app.models import ECCLevel

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "format_mask0_reference_vectors.json").read_text(encoding="utf-8")
)


class FormatInfoTests(unittest.TestCase):
    def test_all_thirty_two_published_vectors(self):
        self.assertEqual(len(_FIXTURE["format_vectors"]), 32)
        for vector in _FIXTURE["format_vectors"]:
            with self.subTest(level=vector["ecc_level"], mask=vector["mask_id"]):
                actual = build_format_bits(ECCLevel(vector["ecc_level"]), vector["mask_id"])
                self.assertEqual("".join(map(str, actual)), vector["bits_msb_first"])
                self.assertIsInstance(actual, tuple)
                self.assertEqual(len(actual), 15)
                self.assertTrue(all(type(bit) is int and bit in (0, 1) for bit in actual))

    def test_l_mask_zero_reference_and_bit_order(self):
        self.assertEqual(build_format_bits("L", 0), tuple(map(int, "111011111000100")))
        self.assertEqual(int("".join(map(str, build_format_bits("L", 0))), 2), 0x77C4)

    def test_enum_and_canonical_string_have_same_result(self):
        for level in ECCLevel:
            self.assertEqual(build_format_bits(level, 0), build_format_bits(level.value, 0))

    def test_wrong_level_types_are_rejected(self):
        for value in (None, 1, True, [], {}):
            with self.subTest(value=value), self.assertRaises(TypeError):
                build_format_bits(value, 0)

    def test_unknown_level_values_are_rejected(self):
        for value in ("", "l", "auto", "1", "L "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_format_bits(value, 0)

    def test_mask_type_rejects_bool_strings_and_numpy_scalars(self):
        for value in (True, False, "0", None, 0.0, np.int64(0)):
            with self.subTest(value=repr(value)), self.assertRaises(TypeError):
                build_format_bits("L", value)

    def test_out_of_range_mask_values_are_rejected(self):
        for value in (-1, 8, 100):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_format_bits("L", value)

    def test_bch_format_codewords_have_minimum_distance_seven(self):
        codewords = [int("".join(map(str, build_format_bits(level, mask))), 2)
                     for level in ECCLevel for mask in range(8)]
        self.assertEqual(len(set(codewords)), 32)
        minimum = min((left ^ right).bit_count()
                      for index, left in enumerate(codewords) for right in codewords[index + 1:])
        self.assertEqual(minimum, 7)
