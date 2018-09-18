
import typing
if typing.TYPE_CHECKING:
    from typing import Any, BinaryIO, Tuple


def encode_multi_byte_int(value: int) -> bytes:
    """Encode an unsigned integer into up to 5 bytes

    :param value: The unsigned integer to encode
    :return: A byte string encoding the given integer
    """
    if value > 2147483647 or value < 0:
        raise ValueError("Can not encode integer of more than 31 bits")

    b5 = ((value >> 28) & 0x03)
    b4 = ((value >> 21) & 0x7F) | (0x80 if b5 > 0 else 0)
    b3 = ((value >> 14) & 0x7F) | (0x80 if b4 > 0 else 0)
    b2 = ((value >> 7) & 0x7F) | (0x80 if b3 > 0 else 0)
    b1 = (value & 0x7F) | (0x80 if b2 > 0 else 0)
    if b5 > 0:
        return bytes((b1, b2, b3, b4, b5))
    if b4 > 0:
        return bytes((b1, b2, b3, b4))
    if b3 > 0:
        return bytes((b1, b2, b3))
    if b2 > 0:
        return bytes((b1, b2))
    return bytes((b1, ))


def write_multi_byte_int(fp: 'BinaryIO', value: int) -> None:
    """Write an unsigned integer to the given stream

    :param fp: The binary stream to write to
    :param value: The unsigned integer to write
    """
    bytes_value = encode_multi_byte_int(value)
    fp.write(bytes_value)


def decode_multi_byte_int(byte_str: bytes) -> 'Tuple[int, int]':
    """Decode a byte string into a multi-byte length

    A multi-byte length may contain up to 5 bytes, of which the lower
    7 bits of each are used to construct the final 31-bit value.

    For each byte, the topmost bit is used to indicate that the encoded
    int continues in the next byte.

    For the 5th byte, the topmost 5 bits must be unset.

    This function returns a tuple of (int, int) encoded as
    (num_bytes, value) where num_bytes is the number of bytes in the
    given byte string used to decode the value, and value is the decoded
    value.

    :param byte_str: A byte string to parse
    :return: A tuple of (int, int), encoded as (num_bytes, value)
    """
    byte_str_len = len(byte_str)
    if byte_str_len == 0:
        raise ValueError("Multi-byte length must be at least 1 byte long")

    value = byte_str[0] & 0x7F
    if not (byte_str[0] & 0x80):
        return 1, value

    if byte_str_len < 2:
        raise ValueError("Expected 2 bytes in multi-byte length, got 1")
    value = value + ((byte_str[1] & 0x7F) << 7)
    if not (byte_str[1] & 0x80):
        return 2, value

    if byte_str_len < 3:
        raise ValueError("Expected 3 bytes in multi-byte length, got 2")
    value = value + ((byte_str[2] & 0x7F) << 14)
    if not (byte_str[2] & 0x80):
        return 3, value

    if byte_str_len < 4:
        raise ValueError("Expected 4 bytes in multi-byte length, got 3")
    value = value + ((byte_str[3] & 0x7F) << 21)
    if not (byte_str[3] & 0x80):
        return 4, value

    if byte_str_len < 5:
        raise ValueError("Expected 5 bytes in multi-byte length, got 4")
    value = value + ((byte_str[4] & 0x7F) << 28)

    if value > 2147483647:
        raise ValueError("Decoded multi-byte length value is > 2**31-1")

    if not (byte_str[4] & 0x80):
        return 5, value

    raise ValueError("Malformed multi-byte length; 5th byte must always be < 128")


def read_multi_byte_int(fp: 'BinaryIO') -> int:
    """Read a multi-byte int from the given stream

    :param fp: The stream to read
    :return: The decoded unsigned integer
    """
    byte_str = fp.read(1)
    if not (byte_str[0] & 0x80):
        return decode_multi_byte_int(byte_str)[1]

    byte_str += fp.read(1)
    if not (byte_str[1] & 0x80):
        return decode_multi_byte_int(byte_str)[1]

    byte_str += fp.read(1)
    if not (byte_str[2] & 0x80):
        return decode_multi_byte_int(byte_str)[1]

    byte_str += fp.read(1)
    if not (byte_str[3] & 0x80):
        return decode_multi_byte_int(byte_str)[1]

    byte_str += fp.read(1)
    return decode_multi_byte_int(byte_str)[1]


def move(instance: 'Any', requested_type: 'type') -> 'Any':
    if type(instance) is requested_type:
        return instance
    return requested_type(instance)
