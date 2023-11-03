from unittest import TestCase

from dynatrace_extension.cli.create import is_pep8_compliant


class TestTemplates(TestCase):
    def test_extension_name(self):
        self.assertFalse(is_pep8_compliant("test-ext"))
        self.assertFalse(is_pep8_compliant("_testext"))
        self.assertFalse(is_pep8_compliant("testext_"))
        self.assertFalse(is_pep8_compliant("test-ext"))
        self.assertFalse(is_pep8_compliant("TestExt"))
        self.assertFalse(is_pep8_compliant("0TestExt"))
        self.assertFalse(is_pep8_compliant("0_test_ext"))

        self.assertTrue(is_pep8_compliant("testext"))
        self.assertTrue(is_pep8_compliant("test_ext"))
        self.assertTrue(is_pep8_compliant("test_ext_name"))
        self.assertTrue(is_pep8_compliant("test1_e2xt_name4"))
