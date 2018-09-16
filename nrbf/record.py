import abc
import io

import nrbf.enum as enums
import nrbf.exceptions as exceptions
import nrbf.primitives as primitives
import nrbf.structures as structs
import nrbf.utils as utils
import nrbf.value

import typing

if typing.TYPE_CHECKING:
    from typing import BinaryIO, List, Optional, Tuple

    from nrbf.enum import BinaryArrayType, BinaryType, PrimitiveType, RecordType
    from nrbf.primitives import Int32, Int32Value, String, StringValue
    from nrbf.structures import ClassInfo, MemberTypeInfo, ExtraInfoType


class Record(nrbf.value.Value, metaclass=abc.ABCMeta):
    @staticmethod
    def read_type(fp: 'BinaryIO', expected: 'RecordType') -> None:
        byte_value = fp.read(1)[0]
        record_type = enums.RecordType(byte_value)
        if record_type != expected:
            raise exceptions.RecordTypeError(expected, record_type)

    @classmethod
    @abc.abstractmethod
    def read(cls, fp: 'BinaryIO', read_type: bool = False):
        raise exceptions.ClassMethodNotImplemented(cls, "read()")

    @property
    @abc.abstractmethod
    def record_type(self) -> 'RecordType':
        raise exceptions.MethodNotImplemented(self, "record_type::get")

    def write(self, fp: 'BinaryIO', write_type: bool = True) -> None:
        if write_type:
            fp.write(self.record_type.to_bytes(1, 'little'))
        fp.write(bytes(self))


class ClassRecord(Record, metaclass=abc.ABCMeta):
    def __init__(self, class_info: 'ClassInfo', library_id: 'Optional[Int32Value]',
                 member_type_info: 'Optional[MemberTypeInfo]') -> None:
        self._class_info = class_info
        self._library_id = utils.move(library_id, primitives.Int32) if library_id is not None else primitives.Int32(-1)
        self._member_type_info = member_type_info

    @property
    def class_info(self) -> 'ClassInfo':
        return self._class_info

    @property
    def member_type_info(self) -> 'Optional[MemberTypeInfo]':
        return self._member_type_info

    @property
    def library_id(self) -> 'Int32':
        return self._library_id

    @property
    def name(self) -> 'String':
        return self._class_info.name

    @property
    def members(self) -> 'List[String]':
        return self._class_info.members

    @property
    def object_id(self) -> 'Int32':
        return self._class_info.object_id

    def __str__(self) -> str:
        return "<Class: {}>".format(self.name)


class ArrayRecord(Record, metaclass=abc.ABCMeta):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool=False) -> 'ArrayRecord':
        object_id = primitives.Int32.read(fp)
        length = primitives.Int32.read(fp)
        return cls(object_id, length)

    def __init__(self, object_id: 'Int32Value', length: 'Int32Value') -> None:
        self._object_id = utils.move(object_id, primitives.Int32)
        self._length = utils.move(length, primitives.Int32)

    @property
    def object_id(self) -> 'Int32':
        return self._object_id

    @property
    def length(self) -> 'Int32':
        return self._length

    def __bytes__(self) -> bytes:
        return bytes(self.object_id) + bytes(self.length)

    def __str__(self) -> str:
        return "{}({}, {})".format(type(self).__name__, self.object_id, self.length)

####################
# Concrete Classes #
####################


class ArraySingleObjectRecord(ArrayRecord):
    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.ArraySingleObject


class ArraySinglePrimitiveRecord(ArrayRecord):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool=False) -> 'ArraySinglePrimitiveRecord':
        object_id = primitives.Int32.read(fp)
        length = primitives.Int32.read(fp)
        type_byte = fp.read(1)[0]
        type_enum = enums.PrimitiveType(type_byte)
        return ArraySinglePrimitiveRecord(object_id, length, type_enum)

    def __init__(self, object_id: 'Int32Value', length: 'Int32Value', type_enum: 'PrimitiveType'):
        ArrayRecord.__init__(self, object_id, length)
        self._type_enum = enums.PrimitiveType(type_enum)

    @property
    def primitive_type(self) -> 'PrimitiveType':
        return self._type_enum

    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.ArraySinglePrimitive

    def __bytes__(self) -> bytes:
        return b''.join((
            bytes(self.object_id),
            bytes(self.length),
            self._type_enum.to_bytes(1, 'little', signed=False)
        ))

    def __repr__(self) -> str:
        return "ArraySinglePrimitive({}, {}, PrimitiveType.{})".format(
            self.object_id, self.length, self._type_enum.name
        )


class ArraySingleStringRecord(ArrayRecord):
    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.ArraySingleString


class BinaryArrayRecord(ArrayRecord):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool = False) -> 'BinaryArrayRecord':
        if read_type:
            Record.read_type(fp, enums.RecordType.BinaryArray)

        object_id = primitives.Int32.read(fp)
        array_type_byte = fp.read(1)[0]
        array_type = enums.BinaryArrayType(array_type_byte)  # type: BinaryArrayType
        rank = primitives.Int32.read(fp)  # type: Int32
        lengths = list()  # type: List[Int32]
        for _ in range(rank.value):
            lengths.append(primitives.Int32.read(fp))

        lower_bounds = None  # type: Optional[List[Int32]]
        if 3 <= array_type <= 5:
            lower_bounds = list()
            for _ in range(rank.value):
                lower_bounds.append(primitives.Int32.read(fp))

        type_enum_byte = fp.read(1)[0]
        type_enum = enums.BinaryType(type_enum_byte)
        extra_info = ExtraInfoType.read(fp, type_enum)
        return BinaryArrayRecord(object_id, array_type, rank, lengths, lower_bounds, type_enum, extra_info)

    def __init__(self, object_id: 'Int32Value', array_type: 'BinaryArrayType', rank: 'Int32Value',
                 lengths: 'List[Int32Value]', lower_bounds: 'Optional[List[Int32Value]]', types: 'BinaryType',
                 extra_info: 'ExtraInfoType') -> None:
        ArrayRecord.__init__(self, object_id, lengths[0])
        self._bin_array_type = enums.BinaryArrayType(array_type)  # type: BinaryArrayType
        self._rank = utils.move(rank, primitives.Int32)  # type: Int32
        self._type = enums.BinaryType(types)
        self._extra_info = extra_info
        if not structs.ExtraTypeInfo.validate(self._type, self._extra_info):
            raise exceptions.InvalidExtraInfoValue(extra_info, self._type)

        self._lengths = lengths  # type: List[Int32]
        if len(self._lengths) != self._rank.value:
            raise ValueError("Length of lengths member must match rank in BinaryArrayRecord")
        for i, length in enumerate(self._lengths):
            self._lengths[i] = utils.move(length, primitives.Int32)

        # The lower_bound of a BinaryArray slice is the index of the
        # first element in the slice.
        self._lower_bounds = lower_bounds
        if 3 <= array_type <= 5:
            if self._lower_bounds is None:
                raise ValueError("BinaryArrayRecord for Offset array must have lower_bounds")
            if len(self._lower_bounds) != self._rank.value:
                raise ValueError("Length of lower_bounds member must match rank in BinaryArrayRecord")
            for i, lower_bound in self._lower_bounds:
                self._lower_bounds[i] = utils.move(lower_bound, primitives.Int32)
        else:
            if self._lower_bounds is not None:
                raise ValueError("BinaryArrayRecord for non-Offset array must not have lower_bounds")

    @property
    def object_id(self) -> 'Int32':
        return self._object_id

    @property
    def array_type(self) -> 'BinaryArrayType':
        return self._bin_array_type

    @property
    def lower_bounds(self) -> 'List[Int32]':
        return self._lower_bounds

    @property
    def rank(self) -> 'Int32':
        return self._rank

    @property
    def lengths(self) -> 'List[Int32]':
        return self._lengths

    @property
    def element_type(self) -> 'BinaryType':
        return self._type

    @property
    def extra_info(self) -> 'ExtraInfoType':
        return self._extra_info

    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.BinaryArray

    def write(self, fp: 'BinaryIO', write_type: bool = True) -> None:
        if write_type:
            fp.write(self.record_type.to_bytes(1, 'little', signed=False))

        self._object_id.write(fp)
        fp.write(self._bin_array_type.to_bytes(1, 'little', signed=False))
        self._rank.write(fp)
        for length in self._lengths:
            length.write(fp)
        if self._lower_bounds is not None:
            for lower_bound in self._lower_bounds:
                lower_bound.write(fp)
        fp.write(self._type.to_bytes(1, 'little', signed=False))
        if self._type == enums.BinaryType.Primitive or self._type == enums.BinaryType.PrimitiveArray:
            fp.write(self._extra_info.to_bytes(1, 'little', signed=False))
        elif self._type == enums.BinaryType.Class or self._type == enums.BinaryType.SystemClass:
            self._extra_info.write(fp)

    def __bytes__(self) -> bytes:
        b_io = io.BytesIO()
        self.write(b_io, False)
        return b_io.getvalue()

    def __repr__(self) -> str:
        return "BinaryArrayRecord({}, BinaryArrayType.{}, {}, {}, {}, BinaryType.{}, {})".format(
            self.object_id, self.array_type.name, self.rank, self.lengths, self.lower_bounds,
            self.element_type.name, self.extra_info
        )


class BinaryLibraryRecord(Record):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool = False) -> 'BinaryLibraryRecord':
        if read_type:
            Record.read_type(fp, enums.RecordType.BinaryLibrary)
        lib_id = nrbf.primitives.Int32.read(fp)
        name = nrbf.primitives.String.read(fp)
        return BinaryLibraryRecord(lib_id, name)

    def __init__(self, lib_id: 'Int32Value', lib_name: 'StringValue') -> None:
        self._library_id = utils.move(lib_id, primitives.Int32)
        self._name = utils.move(lib_name, primitives.String)

    @property
    def library_id(self) -> 'Int32':
        return self._library_id

    @property
    def name(self) -> 'String':
        return self._name

    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.BinaryLibrary

    def __bytes__(self) -> bytes:
        return b''.join((
            bytes(self.library_id),
            bytes(self.name)
        ))

    def __repr__(self) -> str:
        return "BinaryLibraryRecord({}, {})".format(
            self.library_id,
            self.name
        )


class ClassWithIdRecord(Record):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool = False) -> 'ClassWithIdRecord':
        if read_type:
            Record.read_type(fp, enums.RecordType.ClassWithId)

        obj_id = primitives.Int32.read(fp)
        meta_id = primitives.Int32.read(fp)
        return ClassWithIdRecord(obj_id, meta_id)

    def __init__(self, object_id: 'Int32Value', metadata_id: 'Int32Value') -> None:
        self._object_id = utils.move(object_id, primitives.Int32)
        self._metadata_id = utils.move(metadata_id, primitives.Int32)

    @property
    def object_id(self) -> 'Int32':
        return self._object_id

    @property
    def metadata_id(self) -> 'Int32':
        return self._metadata_id

    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.ClassWithId

    def __bytes__(self) -> bytes:
        return b''.join((
            bytes(self.object_id),
            bytes(self.metadata_id)
        ))

    def __repr__(self) -> str:
        return "ClassWithIdRecord({}, {})".format(self.object_id, self.metadata_id)


class ClassWithMembersRecord(ClassRecord):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool = False) -> 'ClassWithMembersRecord':
        if read_type:
            Record.read_type(fp, enums.RecordType.ClassWithMembers)

        class_info = structs.ClassInfo.read(fp)
        library_id = primitives.Int32.read(fp)
        return ClassWithMembersRecord(class_info, library_id)

    def __init__(self, class_info: 'ClassInfo', library_id: 'Int32Value') -> None:
        ClassRecord.__init__(self, class_info, library_id, None)

    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.ClassWithMembers

    def __bytes__(self) -> bytes:
        return b''.join((
            bytes(self.class_info),
            bytes(self.library_id)
        ))

    def __repr__(self) -> str:
        return "ClassWithMembersRecord({}, {})".format(repr(self.class_info), self.library_id)


class ClassWithMembersAndTypesRecord(ClassRecord):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool = False) -> 'ClassWithMembersAndTypesRecord':
        if read_type:
            Record.read_type(fp, enums.RecordType.ClassWithMembersAndTypes)

        class_info = structs.ClassInfo.read(fp)
        member_info = structs.MemberTypeInfo.read(fp, len(class_info.members))
        library_id = primitives.Int32.read(fp)
        return ClassWithMembersAndTypesRecord(class_info, member_info, library_id)

    def __init__(self, class_info: 'ClassInfo', member_info: 'MemberTypeInfo', library_id: 'Int32Value') -> None:
        ClassRecord.__init__(self, class_info, utils.move(library_id, primitives.Int32), member_info)

    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.ClassWithMembersAndTypes

    def __bytes__(self) -> bytes:
        return b''.join((
            bytes(self.class_info),
            bytes(self.member_type_info),
            bytes(self.library_id)
        ))

    def __repr__(self) -> str:
        return "ClassWithMembersAndTypesRecord({}, {}, {})".format(
            repr(self.class_info), repr(self.member_type_info), self.library_id
        )


class MessageEndRecord(Record):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool = False) -> 'MessageEndRecord':
        if read_type:
            Record.read_type(fp, enums.RecordType.MessageEnd)
        return MessageEndRecord()

    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.MessageEnd

    def __bytes__(self) -> bytes:
        return b''

    def __repr__(self) -> str:
        return "MessageEndRecord()"


class SerializedStreamHeader(Record):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool = False) -> 'SerializedStreamHeader':
        if read_type:
            Record.read_type(fp, enums.RecordType.SerializedStreamHeader)

        root_id = primitives.Int32.read(fp)
        header_id = primitives.Int32.read(fp)
        major_version = primitives.Int32.read(fp)
        minor_version = primitives.Int32.read(fp)
        return SerializedStreamHeader(root_id, header_id, major_version, minor_version)

    def __init__(self, root_id: 'Int32Value', header_id: 'Int32Value', major_version: 'Int32Value',
                 minor_version: 'Int32Value') -> None:
        self._root = utils.move(nrbf.primitives.Int32(root_id), primitives.Int32)
        self._header = utils.move(nrbf.primitives.Int32(header_id), primitives.Int32)
        self._major = utils.move(nrbf.primitives.Int32(major_version), primitives.Int32)
        self._minor = utils.move(nrbf.primitives.Int32(minor_version), primitives.Int32)

    @property
    def root_id(self) -> 'Int32':
        return self._root

    @property
    def header_id(self) -> 'Int32':
        return self._header

    @property
    def major_version(self) -> 'Int32':
        return self._major

    @property
    def minor_version(self) -> 'Int32':
        return self._minor

    @property
    def version(self) -> 'Tuple[int, int]':
        return self._major.value, self._minor.value

    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.SerializedStreamHeader

    def __bytes__(self) -> bytes:
        return b''.join((
            bytes(self.root_id),
            bytes(self.header_id),
            bytes(self.major_version),
            bytes(self.minor_version)
        ))

    def __repr__(self) -> str:
        return "SerializedStreamHeader({}, {}, {}, {})".format(
            self.root_id,
            self.header_id,
            self.major_version,
            self.minor_version
        )


class SystemClassWithMembersRecord(ClassRecord):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool = False) -> 'SystemClassWithMembersRecord':
        if read_type:
            Record.read_type(fp, enums.RecordType.SystemClassWithMembers)

        class_info = structs.ClassInfo.read(fp)
        return SystemClassWithMembersRecord(class_info)

    def __init__(self, class_info: 'ClassInfo') -> None:
        ClassRecord.__init__(self, class_info, None, None)

    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.SystemClassWithMembers

    def __bytes__(self) -> bytes:
        return bytes(self.class_info)

    def __repr__(self) -> str:
        return "SystemClassWithMembersRecord({})".format(repr(self.class_info))


class SystemClassWithMembersAndTypesRecord(ClassRecord):
    @classmethod
    def read(cls, fp: 'BinaryIO', read_type: bool = False) -> 'SystemClassWithMembersAndTypesRecord':
        if read_type:
            Record.read_type(fp, enums.RecordType.SystemClassWithMembersAndTypes)

        class_info = structs.ClassInfo.read(fp)
        member_type_info = structs.MemberTypeInfo.read(fp, len(class_info.members))
        return SystemClassWithMembersAndTypesRecord(class_info, member_type_info)

    def __init__(self, class_info: 'ClassInfo', member_type_info: 'MemberTypeInfo') -> None:
        ClassRecord.__init__(self, class_info, None, member_type_info)

    @property
    def record_type(self) -> 'RecordType':
        return enums.RecordType.SystemClassWithMembersAndTypes

    def __bytes__(self) -> bytes:
        return b''.join((
            bytes(self.class_info),
            bytes(self.member_type_info)
        ))

    def __repr__(self) -> str:
        return "SystemClassWithMembersAndTypesRecord({}, {})".format(
            repr(self.class_info),
            repr(self.member_type_info)
        )
