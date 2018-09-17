
import abc
import enum
import struct

import nrbf.enum
import nrbf.utils as utils
import nrbf.value

import typing
if typing.TYPE_CHECKING:
    from typing import Any, BinaryIO, List, Tuple, Type, Union
    from nrbf.enum import PrimitiveType

    BooleanValue = Union[bool, bytes, 'Boolean']
    ByteValue = Union[int, bytes, 'Byte']
    CharValue = Union[int, bytes, str, 'Char']
    DateTimeValue = Union[int, bytes, Tuple[int, 'DateTime.Kind'], 'DateTime']
    DecimalValue = Union[int, float, bytes, str, 'Decimal']
    DoubleValue = Union[float, bytes, 'Double']
    Int8Value = Union[int, bytes, 'Int8']
    Int16Value = Union[int, bytes, 'Int16']
    Int32Value = Union[int, bytes, 'Int32']
    Int64Value = Union[int, bytes, 'Int64']
    SingleValue = Union[float, bytes, 'Single']
    StringValue = Union[str, bytes, 'String']
    TimeSpanValue = Union[int, bytes, 'TimeSpan']
    UInt16Value = Union[int, bytes, 'UInt16']
    UInt32Value = Union[int, bytes, 'UInt32']
    UInt64Value = Union[int, bytes, 'UInt64']

    PrimitiveValue = Union[
        BooleanValue, ByteValue, CharValue, DateTimeValue, DecimalValue, DoubleValue, Int8Value, Int16Value,
        Int32Value, Int64Value, SingleValue, StringValue, TimeSpanValue, UInt16Value, UInt32Value, UInt64Value,
        'Primitive'
    ]


class Primitive(nrbf.value.Value, metaclass=abc.ABCMeta):
    _Types = list()  # type: List[Type[Primitive]]

    @staticmethod
    def get_class(primitive_type: 'PrimitiveType') -> 'Type[Primitive]':
        t = Primitive._Types[primitive_type]
        if t is None:
            raise ValueError("No class associated with {}".format(primitive_type))
        return t

    @classmethod
    @abc.abstractmethod
    def read(cls, fp: 'BinaryIO') -> 'Primitive':
        raise NotImplementedError("{}::read() not implemented".format(cls.__name__))

    @property
    @abc.abstractmethod
    def value(self) -> 'Any':
        raise NotImplementedError("{}::value::get not implemented".format(type(self).__name__))

    @value.setter
    @abc.abstractmethod
    def value(self, new_value: 'Any') -> None:
        raise NotImplementedError("{}::value::set not implemented".format(type(self).__name__))

    @property
    @abc.abstractmethod
    def type(self) -> 'PrimitiveType':
        raise NotImplementedError("{}::type not implemented".format(type(self).__name__))

    def write(self, fp: 'BinaryIO') -> None:
        fp.write(bytes(self))

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return int(self.value)

    def __float__(self) -> float:
        return float(self.value)

    def __bool__(self) -> bool:
        return bool(self.value)

    def __eq__(self, other: 'Any') -> bool:
        if type(other) is Primitive:
            return self.value == other.value
        return self.value == other

    def __ne__(self, other: 'Any') -> bool:
        if type(other) is Primitive:
            return self.value != other.value
        return self.value != other

    def __ge__(self, other: 'Any') -> bool:
        if type(other) is Primitive:
            return self.value >= other.value
        return self.value >= other

    def __gt__(self, other: 'Any') -> bool:
        if type(other) is Primitive:
            return self.value > other.value
        return self.value > other

    def __le__(self, other: 'Any') -> bool:
        if type(other) is Primitive:
            return self.value <= other.value
        return self.value <= other

    def __lt__(self, other: 'Any') -> bool:
        if type(other) is Primitive:
            return self.value < other.value
        return self.value < other


class Boolean(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'Boolean':
        return Boolean(fp.read(1))

    @staticmethod
    def convert(value: 'BooleanValue') -> bool:
        value_type = type(value)
        if value_type is bytes:
            return struct.unpack('?', value)[0]
        if value_type is Boolean:
            return value.value
        return bool(value)

    def __init__(self, value: 'BooleanValue') -> None:
        self._value = Boolean.convert(value)

    @property
    def value(self) -> bool:
        return self._value

    @value.setter
    def value(self, new_value: 'BooleanValue') -> None:
        self._value = Boolean.convert(new_value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.Boolean

    def __bytes__(self) -> bytes:
        return b'\x01' if self._value else b'\x00'

    def __repr__(self) -> str:
        return "Boolean({})".format(self._value)


class Byte(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'Byte':
        return Byte(fp.read(1))

    @staticmethod
    def convert(value: 'ByteValue') -> int:
        value_type = type(value)
        if value_type is bytes:
            if len(value) != 1:
                raise ValueError("Byte requires 1 byte to unpack")
            return struct.unpack('B', value)[0]
        if value_type is int:
            if value > 255:
                return value & 0xFF
            if value < 0:
                return ~((~value) & 0xFF)
            return value
        if value_type is Byte:
            return value.value
        raise TypeError("Byte must be one of bytes, int, or Byte")

    def __init__(self, value: 'ByteValue') -> None:
        self._value = Byte.convert(value)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, new_value) -> None:
        self._value = Byte.convert(new_value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.Byte

    def __bytes__(self) -> bytes:
        return self._value.to_bytes(1, 'little')

    def __repr__(self) -> str:
        return "Byte({})".format(self._value)


class Char(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'Char':
        bytes_value = fp.read(1)
        first_byte = bytes_value[0]
        if first_byte > 127:
            if first_byte >= 0xF0:
                bytes_value = bytes_value + fp.read(3)
            elif first_byte >= 0xE0:
                bytes_value = bytes_value + fp.read(2)
            else:
                bytes_value = bytes_value + fp.read(1)
        return Char(bytes_value)

    @staticmethod
    def convert(value: 'CharValue') -> str:
        value_type = type(value)
        if value_type is int:
            return chr(value)
        if value_type is str:
            if len(value) != 1:
                raise ValueError("Char value must be of length 1")
            return value
        if value_type is bytes:
            unicode_str = value.decode('utf-8')
            if len(unicode_str) != 1:
                raise ValueError("Char value must be of length 1")
            return unicode_str
        if value_type is Char:
            return value.value
        raise TypeError("Char must be one of bytes, int, str, or Char")

    def __init__(self, value: 'CharValue') -> None:
        self._value = Char.convert(value)

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, new_value: 'CharValue') -> None:
        self._value = Char.convert(new_value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.Char

    def __bytes__(self) -> bytes:
        return self._value.encode('utf-8')

    def __repr__(self) -> str:
        return "Char({})".format(self._value)


class DateTime(Primitive):
    @enum.unique
    class Kind(enum.IntEnum):
        NoTimeZone = 0
        UtcTime = 1
        LocalTime = 2

    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'DateTime':
        return DateTime(fp.read(8))

    @staticmethod
    def convert(value: 'DateTimeValue') -> 'Tuple[int, DateTime.Kind]':
        value_type = type(value)
        if value_type is bytes:
            if len(value) != 8:
                raise ValueError("DateTime requires 8 bytes to unpack")
            value = int.from_bytes(value, 'little', signed=True)
            value_type = int

        if value_type is int:
            kind_value = (value & 0xC000000000000000) >> 62
            tick_value = value & 0x3FFFFFFFFFFFFFFF
            return tick_value, DateTime.Kind(kind_value)
        if value_type is tuple:
            if len(value) != 2 or type(value[0]) is not int or type(value[1]) is not DateTime.Kind:
                raise ValueError("DateTime tuple unpacking requires Tuple[int, DateTime.Kind]")
            tick_value = DateTime._adjust_ticks(value[0])
            kind_value = DateTime.Kind(value[1])
            return tick_value, kind_value
        if value_type is DateTime:
            return value.value
        raise TypeError("DateTime must be one of bytes, int, Tuple[int, DateTime.Kind], or DateTime")

    @staticmethod
    def _adjust_ticks(ticks: int) -> int:
        if ticks < -0x2000000000000000:
            ticks = ~((~ticks) & 0x1FFFFFFFFFFFFFFF)
        elif ticks > 0x1FFFFFFFFFFFFFFF:
            ticks = ticks & 0x1FFFFFFFFFFFFFFF
        return ticks

    def __init__(self, value: 'DateTimeValue') -> None:
        self._ticks, self._kind = DateTime.convert(value)

    @property
    def value(self) -> 'Tuple[int, DateTime.Kind]':
        return self._ticks, self._kind

    @value.setter
    def value(self, new_value: 'DateTimeValue') -> None:
        self._ticks, self._kind = DateTime.convert(new_value)

    @property
    def kind(self) -> 'DateTime.Kind':
        return self._kind

    @kind.setter
    def kind(self, new_value: 'DateTime.Kind') -> None:
        self._kind = DateTime.Kind(new_value)

    @property
    def ticks(self) -> int:
        return self._ticks

    @ticks.setter
    def ticks(self, new_value: int) -> None:
        self._ticks = DateTime._adjust_ticks(new_value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.DateTime

    def __bytes__(self) -> bytes:
        return int(self).to_bytes(8, 'little', signed=False)

    def __repr__(self) -> str:
        return "DateTime(({}, DateTime.Kind.{}))".format(self._ticks, self._kind.name)

    def __int__(self) -> int:
        return self._kind << 62 | self._ticks

    def __float__(self) -> float:
        return float(int(self))

    def __bool__(self) -> bool:
        return bool(self._ticks)


class Decimal(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'Decimal':
        length = utils.read_multi_byte_int(fp)
        data = fp.read(length)
        return Decimal(data.decode('utf-8'))

    @staticmethod
    def count_digits(value: str) -> int:
        count = 0
        str_len = len(value)
        for i in range(str_len):
            if 48 <= ord(value[i]) <= 57:
                count += 1
            elif not (value == '.' or value == '+'):
                raise ValueError("Malformed Decimal string")
        return count

    @staticmethod
    def round(value: str) -> str:
        str_len = len(value)
        negative = value[0] == '-'
        if str_len <= 29 or (negative and str_len == 30):
            # Early exit; if we have 29 or less characters, no need to round
            return value

        decimal_idx = -1
        digits = 0
        last_idx = 0
        chars = list()
        for i in range(str_len):
            chars.append(value[i])
            if value[i] == '.':
                decimal_idx = i
            elif 48 <= ord(value[i]) <= 57:
                digits += 1

            if digits == 29:
                last_idx = i
                break

        if last_idx == 0 or len(chars) == str_len:
            # Early exit; we had exactly 29 digits
            return value

        if decimal_idx == -1:
            if negative:
                return "-79228162514264337593543950334"
            return "79228162514264337593543950334"

        next_val = int(value[last_idx + 1])
        if next_val < 5:
            # If our last digit is less than 5, truncate
            return ''.join(chars)

        round_past_decimal = False
        first_digit = 1 if negative else 0
        running = True
        while running and last_idx >= first_digit:
            current = ord(chars[last_idx]) - 48
            current += 1
            if current >= 10:
                current = 0
                running = True
            else:
                running = False
            chars[last_idx] = chr(current + 48)
            if last_idx - 1 == decimal_idx:
                last_idx -= 2
                round_past_decimal = True
            else:
                last_idx -= 1

        if running:
            chars.insert(first_digit, '1')

        if round_past_decimal:
            return ''.join(chars[0:decimal_idx])
        return ''.join(chars[0:last_idx + 2])

    @staticmethod
    def verify(value: str) -> bool:
        digits = 0
        str_len = len(value)
        if str_len == 0:
            return False

        idx = 0
        if value[0] == '-':
            idx += 1
            if str_len == 1:
                return False

        while idx < str_len and 48 <= ord(value[idx]) <= 57:
            idx += 1
            digits += 1

        if idx >= str_len:
            return digits > 0

        if value[idx] == '.':
            if digits == 0 or idx == str_len - 1:
                return False
            idx += 1
        else:
            return False

        while idx < str_len and 48 <= ord(value[idx]) <= 57:
            idx += 1
            digits += 1

        if idx >= str_len:
            return digits > 0
        return False

    @staticmethod
    def convert(value: 'DecimalValue') -> str:
        value_type = type(value)
        if value_type is int:
            if value > 79228162514264337593543950334:
                return "79228162514264337593543950334"
            if value < -79228162514264337593543950334:
                return "-79228162514264337593543950334"
            return str(value)
        if value_type is float:
            if value > 79228162514264337593543950334:
                return "79228162514264337593543950334"
            if value < -79228162514264337593543950334:
                return "-79228162514264337593543950334"
            str_value = str(value)
            return Decimal.round(str_value)
        if value_type is str:
            if not Decimal.verify(value):
                raise ValueError("Invalid Decimal format")
            return Decimal.round(value)
        if value_type is bytes:
            num_bytes, length = utils.decode_multi_byte_int(value)
            str_value = value[num_bytes:].decode('utf-8')
            if not Decimal.verify(str_value):
                raise ValueError("Invalid Decimal format")
            return Decimal.round(value)
        if value_type is Decimal:
            return value.value
        raise TypeError("Decimal value must be one of int, float, str, bytes, or Decimal")

    def __init__(self, value: 'DecimalValue') -> None:
        self._value = Decimal.convert(value)

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, new_value: 'DecimalValue') -> None:
        self._value = Decimal.convert(new_value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.Decimal

    def __bytes__(self) -> bytes:
        len_prefix = utils.encode_multi_byte_int(len(self._value))
        return len_prefix + self._value.encode('utf-8')

    def __repr__(self) -> str:
        return "Decimal({})".format(repr(self._value))


class Double(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'Double':
        return Double(fp.read(8))

    @staticmethod
    def convert(value: 'DoubleValue') -> float:
        value_type = type(value)
        if value_type is float:
            return value
        if value_type is Double:
            return value.value
        if value_type is bytes:
            if len(value) != 8:
                raise ValueError("Double requires 8 bytes to unpack")
            return struct.unpack('d', value)[0]
        raise TypeError("Double must be one of float, bytes, or Double")

    def __init__(self, value: 'DoubleValue') -> None:
        self._value = Double.convert(value)

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, new_value: 'DoubleValue') -> None:
        self._value = Double.convert(new_value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.Double

    def __bytes__(self) -> bytes:
        return struct.pack('d', self._value)

    def __repr__(self) -> str:
        return "Double({})".format(self._value)


class Int8(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'Int8':
        return Int8(fp.read(1))

    @staticmethod
    def convert(value: 'Int8Value') -> int:
        value_type = type(value)
        if value_type is int:
            if value < -128:
                value = ~((~value) & 0x7F)
            elif value > 127:
                value = value & 0x7F
            return value
        if value_type is bytes:
            if len(value) != 1:
                raise ValueError("Int8 requires 1 bytes to unpack")
            return int.from_bytes(value, 'little', signed=True)
        if value_type is Int8:
            return value.value
        raise TypeError("Int8 must be one of int, bytes, Int8")

    def __init__(self, value: 'Int8Value') -> None:
        self._value = Int8.convert(value)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, new_value: 'Int8Value') -> None:
        self._value = Int8.convert(new_value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.SByte

    def __bytes__(self) -> bytes:
        return self._value.to_bytes(1, 'little', signed=True)

    def __repr__(self) -> str:
        return "Int8({})".format(self._value)


class Int16(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'Int16':
        return Int16(fp.read(2))

    @staticmethod
    def convert(value: 'Int16Value') -> int:
        value_type = type(value)
        if value_type is int:
            if value < -32768:
                value = ~((~value) & 0x7FFF)
            elif value > 32767:
                value = value & 0x7FFF
            return value
        if value_type is bytes:
            if len(value) != 2:
                raise ValueError("Int16 requires 2 bytes to unpack")
            return int.from_bytes(value, 'little', signed=True)
        if value_type is Int16:
            return value.value
        raise TypeError("Int16 must be one of int, bytes, Int16")

    def __init__(self, value: 'Int16Value') -> None:
        self._value = Int16.convert(value)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, value: 'Int16Value') -> None:
        self._value = Int16.convert(value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.Int16

    def __bytes__(self) -> bytes:
        return self._value.to_bytes(2, 'little', signed=True)

    def __repr__(self) -> str:
        return "Int16({})".format(self._value)


class Int32(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'Int32':
        return Int32(fp.read(4))

    @staticmethod
    def convert(value: 'Int32Value') -> int:
        value_type = type(value)
        if value_type is int:
            if value > 2147483647:
                value = value & 0x7FFFFFFF
            elif value < -2147483648:
                value = ~((~value) & 0x7FFFFFFF)
            return value
        if value_type is bytes:
            if len(value) != 4:
                raise ValueError("Int32 requires 4 bytes to unpack")
            return int.from_bytes(value, 'little', signed=True)
        if value_type is Int32:
            return int(value)
        raise TypeError("Int32 must be one of int, bytes, or Int32")

    def __init__(self, value: 'Int32Value') -> None:
        self._value = Int32.convert(value)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, value: 'Int32Value') -> None:
        self._value = Int32.convert(value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.Int32

    def __bytes__(self) -> bytes:
        return self._value.to_bytes(4, 'little', signed=True)

    def __repr__(self) -> str:
        return "Int32({})".format(self._value)


class Int64(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'Int64':
        return Int64(fp.read(8))

    @staticmethod
    def convert(value: 'Int64Value') -> int:
        value_type = type(value)
        if value_type is int:
            if value > 9223372036854775807:
                return value & 0x7FFFFFFFFFFFFFFF
            if value < -9223372036854775808:
                return ~((~value) & 0x7FFFFFFFFFFFFFFF)
            return value
        if value_type is bytes:
            if len(value) != 8:
                raise ValueError("Int64 requires 8 bytes to unpack")
            return int.from_bytes(value, 'little', signed=True)
        if value_type is Int64:
            return int(value)
        raise TypeError("Int64 must be one of int, bytes, or Int64")

    def __init__(self, value: 'Int64Value') -> None:
        self._value = Int64.convert(value)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, new_value: 'Int64Value') -> None:
        self._value = Int64.convert(new_value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.Int64

    def __bytes__(self) -> bytes:
        return self._value.to_bytes(8, 'little', signed=True)

    def __repr__(self) -> str:
        return "Int64({})".format(self._value)


class String(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'String':
        length = utils.read_multi_byte_int(fp)
        return String(fp.read(length).decode('utf-8'))

    @staticmethod
    def convert(value: 'StringValue') -> str:
        value_type = type(value)
        if value_type is str:
            return value
        if value_type is String:
            return str(value)
        if value_type is bytes:
            read, length = utils.decode_multi_byte_int(value)
            if len(value) != read + length:
                raise ValueError("String expected {} bytes, got {}".format(read + length, len(value)))
            return value[read:].decode('utf-8')
        raise TypeError("String must be one of str, bytes, or LengthPrefixedString")

    def __init__(self, value: 'StringValue') -> None:
        self._value = String.convert(value)

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, value: 'StringValue') -> None:
        self._value = String.convert(value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.String

    def __bytes__(self) -> bytes:
        value = self._value.encode('utf-8')
        length = utils.encode_multi_byte_int(len(value))
        return length + value

    def __repr__(self) -> str:
        return "String({})".format(repr(self._value))


class Single(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'Single':
        return Single(fp.read(4))

    @staticmethod
    def convert(new_value: 'SingleValue') -> float:
        if type(new_value) is float:
            return new_value
        if type(new_value) is Single:
            return float(new_value)
        if type(new_value) is bytes:
            if len(new_value) != 4:
                raise ValueError("Single requires 4 bytes to unpack")
            return struct.unpack("f", new_value)[0]
        raise TypeError("Single must be one of float, bytes, or Single")

    def __init__(self, value: 'SingleValue') -> None:
        self._value = Single.convert(value)

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, new_value: 'StringValue') -> None:
        self._value = Single.convert(new_value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.Single

    def __bytes__(self) -> bytes:
        return struct.pack('f', self._value)

    def __repr__(self) -> str:
        return "Single({})".format(self._value)


class TimeSpan(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'TimeSpan':
        return TimeSpan(fp.read(8))

    @staticmethod
    def convert(value: 'TimeSpanValue') -> int:
        value_type = type(value)
        if value_type is int:
            if value > 9223372036854775807:
                return value & 0x7FFFFFFFFFFFFFFF
            if value < -9223372036854775808:
                return ~((~value) & 0x7FFFFFFFFFFFFFFF)
            return value
        if value_type is bytes:
            if len(value) != 8:
                raise ValueError("TimeSpan requires 8 bytes to unpack")
            return int.from_bytes(value, 'little', signed=False)
        if value_type is TimeSpan:
            return int(value)
        raise TypeError("TimeSpan must be one of int, bytes, or TimeSpan")

    def __init__(self, value: 'TimeSpanValue') -> None:
        self._value = TimeSpan.convert(value)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, new_value: 'TimeSpanValue') -> None:
        self._value = TimeSpan.convert(new_value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.TimeSpan

    def __bytes__(self) -> bytes:
        return self._value.to_bytes(8, 'little', signed=False)

    def __repr__(self) -> str:
        return "TimeSpan({})".format(self._value)


class UInt16(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'UInt16':
        return UInt16(fp.read(2))

    @staticmethod
    def convert(value: 'UInt16Value') -> int:
        value_type = type(value)
        if value_type is int:
            if value > 65535:
                return value & 0xFFFF
            if value < 0:
                return ~((~value) & 0xFFFF)
            return value
        if value_type is bytes:
            if len(value) != 2:
                raise ValueError("UInt16 requires 2 bytes to unpack")
            return int.from_bytes(value, 'little', signed=False)
        if value_type is UInt16:
            return int(value)
        raise TypeError("UInt16 must be one of int, bytes, or UInt16")

    def __init__(self, value: 'UInt16Value') -> None:
        self._value = UInt16.convert(value)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, value: 'UInt16Value') -> None:
        self._value = UInt16.convert(value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.UInt16

    def __bytes__(self) -> bytes:
        return self._value.to_bytes(2, 'little', signed=False)

    def __repr__(self) -> str:
        return "UInt16({})".format(self._value)


class UInt32(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'UInt32':
        return UInt32(fp.read(4))

    @staticmethod
    def convert(value: 'UInt32Value') -> int:
        value_type = type(value)
        if value_type is int:
            if value > 4294967295:
                return value & 0xFFFFFFFF
            if value < 0:
                return ~((~value) & 0xFFFFFFFF)
            return value
        if value_type is bytes:
            if len(value) != 4:
                raise ValueError("UInt32 requires 4 bytes to unpack")
            return int.from_bytes(value, 'little', signed=False)
        if value_type is UInt32:
            return int(value)
        raise TypeError("UInt32 must be one of int, bytes, or UInt32")

    def __init__(self, value: 'UInt32Value') -> None:
        self._value = UInt32.convert(value)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, value: 'UInt32Value') -> None:
        self._value = UInt32.convert(value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.UInt32

    def __bytes__(self) -> bytes:
        return self._value.to_bytes(4, 'little', signed=False)

    def __repr__(self) -> str:
        return "UInt32({})".format(self._value)


class UInt64(Primitive):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'UInt64':
        return UInt64(fp.read(8))

    @staticmethod
    def convert(value: 'UInt64Value') -> int:
        value_type = type(value)
        if value_type is int:
            if value > 18446744073709551615:
                return value & 0xFFFFFFFFFFFFFFFF
            if value < 0:
                return ~((~value) & 0xFFFFFFFFFFFFFFFF)
            return value
        if value_type is bytes:
            if len(value) != 8:
                raise ValueError("UInt64 requires 8 bytes to unpack")
            return int.from_bytes(value, 'little', signed=False)
        if value_type is UInt64:
            return int(value)
        raise TypeError("UInt64 must be one of int, bytes, or UInt64")

    def __init__(self, value: 'UInt64Value') -> None:
        self._value = UInt64.convert(value)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, value: 'UInt64Value') -> None:
        self._value = UInt64.convert(value)

    @property
    def type(self) -> 'PrimitiveType':
        return nrbf.enum.PrimitiveType.UInt64

    def __bytes__(self) -> bytes:
        return self._value.to_bytes(8, 'little', signed=False)

    def __repr__(self) -> str:
        return "UInt64({})".format(self._value)


Primitive._Types = [
    None,
    Boolean,
    Byte,
    Char,
    None,
    Decimal,
    Double,
    Int16,
    Int32,
    Int64,
    Int8,
    Single,
    TimeSpan,
    DateTime,
    UInt16,
    UInt32,
    UInt64,
    None,
    String
]
