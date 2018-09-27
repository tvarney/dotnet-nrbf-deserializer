
import unittest

import dotnet.utils as utils


class TestUtils(unittest.TestCase):
    def test_encode_multi_byte_int32(self):
        self.assertEqual(utils.encode_multi_byte_int(10), b'\x0A')
