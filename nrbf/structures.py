
import io

import nrbf.enum as enums
import nrbf.primitives as primitives
import nrbf.utils as utils

import typing
if typing.TYPE_CHECKING:
    from typing import BinaryIO, List, Union
    from nrbf.enum import BinaryType, PrimitiveType
    from nrbf.primitives import Int32, Int32Value, String, StringValue

    ExtraInfoType = Union[PrimitiveType, String, 'ClassTypeInfo', None]


class ExtraTypeInfo(object):
    @staticmethod
    def read(fp: 'BinaryIO', bin_type: 'BinaryType') -> 'ExtraInfoType':
        if bin_type == enums.BinaryType.Primitive or bin_type == enums.BinaryType.PrimitiveArray:
            byte_value = fp.read(1)[0]
            primitive_type = enums.PrimitiveType(byte_value)
            return primitive_type
        elif bin_type == enums.BinaryType.SystemClass:
            return primitives.String.read(fp)
        elif bin_type == enums.BinaryType.Class:
            return ClassTypeInfo.read(fp)
        return None

    @staticmethod
    def validate(bin_type: 'BinaryType', value: 'ExtraInfoType') -> bool:
        value_type = type(value)
        if bin_type == enums.BinaryType.Primitive or bin_type == enums.BinaryType.PrimitiveArray:
            return value_type is enums.PrimitiveType
        if bin_type == enums.BinaryType.SystemClass:
            return value_type is primitives.String
        if bin_type == enums.BinaryType.Class:
            return value_type is ClassTypeInfo
        return value is None

    def __init__(self) -> None:
        raise NotImplementedError("ExtraTypeInfo::__init__() not implemented")


class ClassTypeInfo(object):
    """Class information for a Member definition

    This structure is found in the MemberTypeInfo of a ClassRecord, and
    it defines a unique class to be used for that member.
    """

    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'ClassTypeInfo':
        class_name = primitives.String.read(fp)
        library_id = primitives.Int32.read(fp)
        return ClassTypeInfo(class_name, library_id)

    def __init__(self, class_name: 'StringValue', library_id: 'Int32Value') -> None:
        self._class_name = utils.move(class_name, primitives.String)
        self._library_id = utils.move(library_id, primitives.Int32)

    @property
    def class_name(self) -> 'String':
        return self._class_name

    @property
    def library_id(self) -> 'Int32':
        return self._library_id

    def write(self, fp: 'BinaryIO') -> None:
        fp.write(bytes(self))

    def __bytes__(self) -> bytes:
        return b''.join((
            bytes(self._class_name),
            bytes(self._library_id)
        ))


class ClassInfo(object):
    @classmethod
    def read(cls, fp: 'BinaryIO') -> 'ClassInfo':
        object_id = primitives.Int32.read(fp)
        name = primitives.String.read(fp)
        member_count = primitives.Int32.read(fp).value
        members = list()
        for _ in range(member_count):
            members.append(primitives.String.read(fp))
        return ClassInfo(object_id, name, members)

    def __init__(self, object_id: 'Int32Value', name: 'StringValue', members: 'List[StringValue]') -> None:
        self._object_id = utils.move(object_id, primitives.Int32)  # type: Int32
        self._name = utils.move(name, primitives.String)  # type: String
        self._members = members  # type: List[String]
        for idx, member in enumerate(self._members):
            self._members[idx] = utils.move(member, primitives.String)

    @property
    def object_id(self) -> 'Int32':
        return self._object_id

    @property
    def name(self) -> 'String':
        return self._name

    @property
    def members(self) -> 'List[String]':
        return self._members

    def write(self, fp: 'BinaryIO') -> None:
        self.object_id.write(fp)
        self.name.write(fp)
        fp.write(len(self._members).to_bytes(4, 'little', signed=True))
        for member_name in self._members:
            member_name.write(fp)

    def __bytes__(self) -> bytes:
        b_io = io.BytesIO()
        self.write(b_io)
        return b_io.getvalue()


class MemberTypeInfo(object):
    @classmethod
    def read(cls, fp: 'BinaryIO', count: int) -> 'MemberTypeInfo':
        bin_types = list()  # type: List[BinaryType]
        extra_info = list()
        for _ in range(count):
            byte_value = fp.read(1)[0]
            bin_type = enums.BinaryType(byte_value)
            bin_types.append(bin_type)

        for bin_type in bin_types:
            extra_info.append(ExtraTypeInfo.read(fp, bin_type))
        return MemberTypeInfo(bin_types, extra_info)

    def __init__(self, bin_types: 'List[BinaryType]', extra_info: 'List[ExtraInfoType]') -> None:
        self._bin_types = bin_types
        self._extra_info = extra_info

    @property
    def binary_types(self) -> 'List[BinaryType]':
        return self._bin_types

    @property
    def extra_info(self) -> 'List[ExtraInfoType]':
        return self._extra_info

    def write(self, fp: 'BinaryIO') -> None:
        for bin_type in self._bin_types:
            fp.write(bin_type.to_bytes(1, 'little', signed=False))

        for info in self._extra_info:
            value_type = type(info)
            if value_type is enums.PrimitiveType:
                fp.write(info.to_bytes(1, 'little', signed=False))
            elif value_type is primitives.String:
                info.write(fp)
            elif value_type is ClassTypeInfo:
                info.write(fp)
            elif info is None:
                pass
            else:
                raise TypeError("Unexpected type {} in MemberTypeInfo.extra_info".format(value_type.__name__))

    def __bytes__(self) -> bytes:
        b_io = io.BytesIO()
        self.write(b_io)
        return b_io.getvalue()
