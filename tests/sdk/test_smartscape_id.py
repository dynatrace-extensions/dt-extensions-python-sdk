import unittest

from dynatrace_extension import smartscape_id
from dynatrace_extension.sdk.smartscape_id import (
    MAX_VALUE_BYTES,
    rule_keys_hash,
    smartscape_id_hex,
    smartscape_id_long,
)


class TestSmartscapeId(unittest.TestCase):
    def test_golden_vector(self):
        self.assertEqual(smartscape_id("TYPE", {"key1": "A", "key2": "B"}), "TYPE-8B775215A352336E")

    def test_hex_matches_full_id(self):
        components = {"key1": "A", "key2": "B"}
        self.assertEqual(smartscape_id("TYPE", components), f"TYPE-{smartscape_id_hex('TYPE', components)}")

    def test_hex_is_16_upper_digits(self):
        value = smartscape_id_hex("TYPE", {"key1": "A"})
        self.assertEqual(len(value), 16)
        self.assertEqual(value, value.upper())

    def test_long_is_signed_hex(self):
        components = {"key1": "A", "key2": "B"}
        unsigned = int(smartscape_id_hex("TYPE", components), 16)
        expected = unsigned - 2**64 if unsigned >= 2**63 else unsigned
        self.assertEqual(smartscape_id_long("TYPE", components), expected)

    def test_component_order_is_significant(self):
        forward = smartscape_id("TYPE", {"key1": "A", "key2": "B"})
        reversed_ = smartscape_id("TYPE", {"key2": "B", "key1": "A"})
        self.assertNotEqual(forward, reversed_)

    def test_empty_components_raises(self):
        with self.assertRaises(ValueError):
            smartscape_id("TYPE", {})

    def test_oversized_value_raises(self):
        with self.assertRaises(ValueError):
            smartscape_id("TYPE", {"key1": "x" * (MAX_VALUE_BYTES + 1)})

    def test_rule_keys_hash_empty_raises(self):
        with self.assertRaises(ValueError):
            rule_keys_hash([])


if __name__ == "__main__":
    unittest.main()
