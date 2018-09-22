
import dotnet.enum as enums
import dotnet.exceptions as exceptions

import typing
if typing.TYPE_CHECKING:
    from typing import List, Union
    from dotnet.enum import BinaryType, PrimitiveType

    ExtraInfoType = Union[PrimitiveType, str, 'ClassTypeInfo', None]


class ExtraTypeInfo(object):
    @staticmethod
    def validate(bin_type: 'BinaryType', value: 'ExtraInfoType') -> bool:
        value_type = type(value)
        if bin_type == enums.BinaryType.Primitive or bin_type == enums.BinaryType.PrimitiveArray:
            return value_type is enums.PrimitiveType
        if bin_type == enums.BinaryType.SystemClass:
            return value_type is str
        if bin_type == enums.BinaryType.Class:
            return value_type is ClassTypeInfo
        return value is None

    @staticmethod
    def check(bin_type: 'BinaryType', value: 'ExtraInfoType') -> None:
        if not ExtraTypeInfo.validate(bin_type, value):
            raise exceptions.InvalidExtraInfoValue(value, bin_type)

    def __init__(self) -> None:
        raise NotImplementedError("ExtraTypeInfo::__init__() not implemented")


class ClassTypeInfo(object):
    """Class information for a Member definition

    This structure is found in the MemberTypeInfo of a ClassRecord, and
    it defines a unique class to be used for that member.
    """

    def __init__(self, class_name: str, library_id: int) -> None:
        self._class_name = class_name
        self._library_id = library_id

    @property
    def class_name(self) -> str:
        return self._class_name

    @property
    def library_id(self) -> int:
        return self._library_id


class ClassInfo(object):
    def __init__(self, object_id: int, name: str, members: 'List[str]') -> None:
        self._object_id = int(object_id)
        self._name = str(name)
        self._members = members  # type: List[str]

    @property
    def object_id(self) -> int:
        return self._object_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def members(self) -> 'List[str]':
        return self._members


class MemberTypeInfo(object):
    def __init__(self, bin_types: 'List[BinaryType]', extra_info: 'List[ExtraInfoType]') -> None:
        self._bin_types = bin_types
        self._extra_info = extra_info

    @property
    def binary_types(self) -> 'List[BinaryType]':
        return self._bin_types

    @property
    def extra_info(self) -> 'List[ExtraInfoType]':
        return self._extra_info


class NullReferenceMultiple(object):
    def __init__(self, count: int) -> None:
        self._count = count

    def __iter__(self) -> 'typing.Iterator':
        for _ in range(self._count):
            yield None

    def __len__(self) -> int:
        return self._count

    def __repr__(self) -> str:
        return "NullReferenceMultiple({})".format(self._count)

    def __str__(self) -> str:
        return "[None]*{}".format(self._count)

