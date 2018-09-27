
import io
import unittest

from dotnet.io.binary import BinaryFormatter
from dotnet.primitives import *


class TestBinaryFormatter(unittest.TestCase):
    def test_read(self):
        bf = BinaryFormatter()
        missing_root_object_fp = io.BytesIO(b'\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x0B')
        string_root_object_fp = io.BytesIO(b''.join((
            b'\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00',
            b'\x06\x01\x00\x00\x00\x0BHello World',
            b'\x0B'
        )))
        extra_information_fp = io.BytesIO(string_root_object_fp.getvalue() + b'\x00\x00\x00\x00')
        bad_header_record_id_fp = io.BytesIO(b'\x01\x00\x00\x00\x00\x00\x00\x00\x00')
        bad_major_version_fp = io.BytesIO(b'\x00\x01\x00\x00\x00\x01\x00\x00\x00\x50\x00\x00\x00\x00\x00\x00\x00')
        bad_minor_version_fp = io.BytesIO(b'\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x50\x00\x00\x00')

        # Working cases
        self.assertEqual(bf.read(string_root_object_fp)[0], "Hello World")
        self.assertEqual(bf.read(extra_information_fp)[0], "Hello World")

        # Missing record
        self.assertRaises(KeyError, bf.read, missing_root_object_fp)
        # Bad header record byte
        self.assertRaises(IOError, bf.read, bad_header_record_id_fp)
        # Bad header major version
        self.assertRaises(IOError, bf.read, bad_major_version_fp)
        # Bad header minor version
        self.assertRaises(IOError, bf.read, bad_minor_version_fp)

    def test_read_char(self):
        bf = BinaryFormatter()

        self.assertEqual(bf.read_char(io.BytesIO(b'!\xF6')), Char("!"))
        self.assertEqual(bf.read_char(io.BytesIO(chr(0xff5f).encode('utf-8') + b'\xF6')), Char(chr(0xff5f)))
        self.assertRaises(UnicodeDecodeError, bf.read_char, io.BytesIO(b'\xF0'))

    def test_read_string_raw(self):
        bf = BinaryFormatter()

        self.assertEqual(bf.read_string_raw(io.BytesIO(b'\x05hello\x00\x00')), "hello")
        self.assertEqual(bf.read_string_raw(io.BytesIO(b'\xC8\x01' + b'a' * 200 + b'\x00')), 'a' * 200)
        self.assertRaises(IOError, bf.read_string_raw, io.BytesIO(b'\xC8\x01\x00\x00'))
