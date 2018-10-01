
import io
import unittest

from dotnet.io.binary import BinaryReader
from dotnet.primitives import *


class TestBinaryFormatter(unittest.TestCase):
    def test_read(self):
        bf = BinaryReader()

        valid_header = b'\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00'
        bin_string_record = b'\06\x01\x00\x00\x00\x0BHello World'
        message_end = b'\x0B'

        missing_root_object = b''.join((valid_header, message_end))
        string_root_object = b''.join((
            valid_header,
            bin_string_record,
            message_end
        ))
        extra_information = b''.join((valid_header, bin_string_record, message_end, b'\x00\x00\x00\x00'))
        bad_header_record_id = b'\x01\x00\x00\x00\x00\x00\x00\x00\x00'
        bad_major_version = b'\x00\x01\x00\x00\x00\x01\x00\x00\x00\x50\x00\x00\x00\x00\x00\x00\x00'
        bad_minor_version = b'\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x50\x00\x00\x00'

        # Working cases
        self.assertEqual(bf.read(io.BytesIO(string_root_object))[0], "Hello World")
        self.assertEqual(bf.read(io.BytesIO(extra_information))[0], "Hello World")

        # Missing record
        self.assertRaises(KeyError, bf.read, io.BytesIO(missing_root_object))
        # Bad header record byte
        self.assertRaises(IOError, bf.read, io.BytesIO(bad_header_record_id))
        # Bad header major version
        self.assertRaises(IOError, bf.read, io.BytesIO(bad_major_version))
        # Bad header minor version
        self.assertRaises(IOError, bf.read, io.BytesIO(bad_minor_version))

    def test_read_char(self):
        bf = BinaryReader()

        self.assertEqual(bf.read_char(io.BytesIO(b'!\xF6')), Char("!"))
        self.assertEqual(bf.read_char(io.BytesIO(chr(0xff5f).encode('utf-8') + b'\xF6')), Char(chr(0xff5f)))
        self.assertRaises(UnicodeDecodeError, bf.read_char, io.BytesIO(b'\xF0'))

    def test_read_string_raw(self):
        bf = BinaryReader()

        self.assertEqual(bf.read_string_raw(io.BytesIO(b'\x05hello\x00\x00')), "hello")
        self.assertEqual(bf.read_string_raw(io.BytesIO(b'\xC8\x01' + b'a' * 200 + b'\x00')), 'a' * 200)
        self.assertRaises(IOError, bf.read_string_raw, io.BytesIO(b'\xC8\x01\x00\x00'))
