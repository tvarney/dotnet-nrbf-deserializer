
import io
import unittest

import dotnet.utils as utils


class TestUtils(unittest.TestCase):
    def test_encode_multi_byte_int32(self):
        self.assertEqual(utils.encode_multi_byte_int(10), b'\x0A')
        self.assertEqual(utils.encode_multi_byte_int(300), b'\xAC\x02')
        self.assertEqual(utils.encode_multi_byte_int(32836), b'\xC4\x80\x02')
        self.assertEqual(utils.encode_multi_byte_int(8381828), b'\x84\xCB\xFF\x03')
        self.assertEqual(utils.encode_multi_byte_int(536778039), b'\xB7\xAA\xFA\xFF\x01')
        self.assertRaises(ValueError, utils.encode_multi_byte_int, 2**32-1)
        self.assertRaises(ValueError, utils.encode_multi_byte_int, -1)

    def test_decode_multi_byte_int32(self):
        self.assertEqual(utils.decode_multi_byte_int(b'\x0A'), (1, 10))
        self.assertEqual(utils.decode_multi_byte_int(b'\xAC\x02'), (2, 300))
        self.assertEqual(utils.decode_multi_byte_int(b'\xC4\x80\x02'), (3, 32836))
        self.assertEqual(utils.decode_multi_byte_int(b'\x84\xCB\xFF\x03'), (4, 8381828))
        self.assertEqual(utils.decode_multi_byte_int(b'\xB7\xAA\xFA\xFF\x01'), (5, 536778039))
        self.assertRaises(ValueError, utils.decode_multi_byte_int, b'\x80\x80\x80\x80\x80\x01')

    def test_write_multi_byte_int32(self):
        b_io = io.BytesIO()
        utils.write_multi_byte_int(b_io, 32836)
        self.assertEqual(b_io.getvalue(), b'\xC4\x80\x02')

    def test_read_multi_byte_int32(self):
        b_io = io.BytesIO(b'\xC4\x80\x02hello')
        self.assertEqual(utils.read_multi_byte_int(b_io), 32836)
        self.assertRaises(IOError, utils.read_multi_byte_int, io.BytesIO(b'\xC4\x80'))
