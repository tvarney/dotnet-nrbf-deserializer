
import abc
import io

import dotnet.enum as enums
import dotnet.exceptions as exception
import dotnet.primitives as primitive
import dotnet.record as record
import dotnet.structures as structs
import dotnet.utils as utils
import dotnet.value

import typing
if typing.TYPE_CHECKING:
    from typing import Any, BinaryIO, Dict, List, Tuple, Union
    from dotnet.enum import BinaryType
    from dotnet.primitives import Int32, Int32Value, Primitive, PrimitiveValue
    from dotnet.record import ArrayRecord, ArraySingleObjectRecord, ArraySinglePrimitiveRecord, \
        ArraySingleStringRecord, ClassRecord, Record
    from dotnet.structures import ExtraInfoType
    from dotnet.value import Value


class DataStore(object):
    def __init__(self) -> None:
        self._records = list()  # type: List[Record]
        self._libraries = {-1: "System"}  # type: Dict[int, str]
        self._objects = dict()  # type: Dict[int, Instance]
        self._classes = dict()  # type: Dict[Tuple[int, str], ClassObject]
        self._known_metadata = dict()  # type: Dict[Tuple[str, str], object]

    @property
    def records(self) -> 'List[Record]':
        return self._records

    @property
    def libraries(self) -> 'Dict[int, str]':
        return self._libraries

    @property
    def objects(self) -> 'Dict[int, Instance]':
        return self._objects

    @property
    def classes(self) -> 'Dict[Tuple[int, str], ClassObject]':
        return self._classes

    def read_file(self, filename: str, clear_records: bool=True) -> int:
        with open(filename, 'rb') as fp:
            return self.read_stream(fp, clear_records)

    def build_class(self, class_record: 'ClassRecord') -> 'ClassObject':
        class_name = class_record.name.value
        library_id = class_record.library_id.value
        member_type_info = class_record.member_type_info
        partial = member_type_info is None
        if partial:
            library_name = self._libraries[library_id]
            key = library_name, class_name
            member_type_info = self._known_metadata.get(key, None)
            if member_type_info is None:
                raise IOError("Partial Class definition encountered with unknown member type information")

        bin_type_len = len(member_type_info.binary_types)
        member_len = len(class_record.members)
        if bin_type_len != member_len:
            raise ValueError("Mismatch in member length and member type info length")

        members = list()  # type: List[Member]
        for i in range(member_len):
            member_name = class_record.members[i].value
            member_bin_type = member_type_info.binary_types[i]
            member_extra_info = member_type_info.extra_info[i]
            members.append(Member(i, member_name, member_bin_type, member_extra_info))

        class_object = ClassObject(class_name, members, partial, library_id)
        old_class_object = self._classes.get((library_id, class_name), None)
        if old_class_object is not None:
            if old_class_object != class_object:
                raise ValueError("Non-equal duplicate class definition")
            return old_class_object
        else:
            self._classes[library_id, class_name] = class_object
        return class_object

    def read_stream(self, fp: 'BinaryIO', clear_records: bool=True) -> int:
        records_read = 0
        if clear_records:
            self._records.clear()

        record_type_byte = fp.read(1)[0]
        record_type = enums.RecordType(record_type_byte)
        if record_type != enums.RecordType.SerializedStreamHeader:
            raise IOError("Expected first record of stream to be SerializedStreamHeader")

        while record_type != enums.RecordType.MessageEnd:
            record_class = record.Record.get_class(record_type)
            record_instance = record_class.read(fp, False)
            records_read += 1
            self._records.append(record_instance)
            if issubclass(record_class, record.ClassRecord):
                class_record = record_instance  # type: ClassRecord
                class_object = self.build_class(class_record)
                class_instance = class_object.read_instance(fp, self, class_record.object_id)
                self._objects[class_record.object_id.value] = class_instance
            elif issubclass(record_class, record.ArrayRecord):
                array_record = record_instance  # type: ArrayRecord
                array_instance = ArrayInstance.read(fp, self, array_record)
                self._objects[array_instance.object_id] = array_instance
            elif record_class is record.BinaryLibraryRecord:
                library_record = record_instance  # type: record.BinaryLibraryRecord
                self._libraries[library_record.library_id.value] = library_record.name.value

            record_type_byte = fp.read(1)[0]
            record_type = enums.RecordType(record_type_byte)

        return records_read


class Instance(dotnet.value.Value, metaclass=abc.ABCMeta):
    def __init__(self, object_id: 'Int32Value') -> None:
        self._object_id = utils.move(object_id, primitive.Int32)  # type: Int32

    @property
    def object_id(self) -> int:
        return self._object_id.value

    @object_id.setter
    def object_id(self, new_object_id: 'Int32Value') -> None:
        self._object_id.value = new_object_id


class ArrayInstance(Instance, metaclass=abc.ABCMeta):
    @staticmethod
    def read(fp: 'BinaryIO', data_store: 'DataStore', array_record: 'ArrayRecord') -> 'ArrayInstance':
        if array_record.record_type == enums.RecordType.ArraySinglePrimitive:
            array_record: ArraySinglePrimitiveRecord
            return PrimitiveArray.read(fp, data_store, array_record)
        if array_record.record_type == enums.RecordType.ArraySingleObject:
            pass
        if array_record.record_type == enums.RecordType.ArraySingleString:
            pass
        if array_record.record_type == enums.RecordType.BinaryArray:
            pass


class ObjectArray(ArrayInstance):
    def __init__(self, object_id: 'Int32Value', data: 'List[Any]'):
        ArrayInstance.__init__(self, object_id)
        self._data = data

    def __getitem__(self, index: int) -> 'Any':
        return self._data[index]


class PrimitiveArray(ArrayInstance):
    @staticmethod
    def read(fp: 'BinaryIO', data_store: 'DataStore', array_record: 'ArraySinglePrimitiveRecord') -> 'PrimitiveArray':
        primitive_type = array_record.primitive_type
        primitive_class = primitive.Primitive.get_class(primitive_type)
        data = list()  # type: List[Primitive]
        for _ in range(array_record.length.value):
            data.append(primitive_class.read(fp))
        return PrimitiveArray(array_record.object_id, primitive_class, data)

    def __init__(self, object_id: 'Int32Value', primitive_class: type, data: 'List[Primitive]') -> None:
        ArrayInstance.__init__(self, object_id)
        self._data_class = primitive_class
        self._data = data

    @property
    def primitive_class(self) -> type:
        return self._data_class

    def write(self, fp: 'BinaryIO') -> None:
        fp.write(enums.RecordType.ArraySinglePrimitive.to_bytes(1, 'little', signed=False))
        fp.write(bytes(self.object_id))
        fp.write(len(self._data).to_bytes(4, 'little', signed=True))
        for item in self._data:
            fp.write(bytes(item))

    def __getitem__(self, index: int) -> 'Primitive':
        return self._data[index]

    def __setitem__(self, index: int, new_data: 'PrimitiveValue') -> None:
        self._data[index].value = utils.move(new_data, self._data_class)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):
        for value in self._data:
            yield value

    def __bytes__(self) -> bytes:
        b_io = io.BytesIO()
        self.write(b_io)
        return b_io.getvalue()


class ClassInstance(Instance):
    def __init__(self, object_id: 'Int32Value', class_object: 'ClassObject', member_data: 'List[Value]') -> None:
        Instance.__init__(self, object_id)
        self._class_object = class_object
        self._member_data = member_data

    @property
    def class_object(self) -> 'ClassObject':
        return self._class_object

    @property
    def member_data(self) -> 'List[Value]':
        return self._member_data

    def __getitem__(self, key: 'Union[int, str]') -> 'Value':
        if type(key) is int:
            return self._member_data[key]
        member_idx = self._class_object.get_member(key).index
        return self._member_data[member_idx]

    def write(self, fp: 'BinaryIO') -> None:
        pass

    def __bytes__(self) -> bytes:
        b_io = io.BytesIO()
        self.write(b_io)
        return b_io.getvalue()


class ClassObject(dotnet.value.Value):
    SystemClass = -1

    def __init__(self, name: str, members: 'List[Member]', partial: bool, library: int=-1) -> None:
        """Create a new Class object

        :param name: The name of the class
        :param members: The data members of the object
        :param partial: If the class should be written without types
        :param library: The id of the library this class came from
        """
        self._name = str(name)
        self._members = members
        self._partial = bool(partial)
        self._library = int(library)
        self._lookup = dict()  # Dict[str, Member]
        for member in self._members:
            self._lookup[member.name] = member

    @property
    def name(self) -> str:
        return self._name

    @property
    def members(self) -> 'List[Member]':
        return self._members

    @property
    def library(self) -> int:
        return self._library

    @property
    def partial(self) -> bool:
        return self._partial

    def get_member(self, member_name: str) -> 'Member':
        return self._lookup[member_name]

    def read_instance(self, fp: 'BinaryIO', data_store: 'DataStore', object_id: 'Int32Value') -> 'ClassInstance':
        member_data = list()  # type: List[Value]
        for member in self._members:
            member_data.append(member.read(fp, data_store))

        return ClassInstance(object_id, self, member_data)

    def write(self, fp: 'BinaryIO'):
        fp.write(bytes(self))

    def __bytes__(self) -> bytes:
        return b''

    def __eq__(self, other: 'Any') -> bool:
        if type(other) is not ClassObject:
            return False
        class_obj = other  # type: ClassObject
        if class_obj.library != self.library:
            return False
        if class_obj.name != self.name:
            return False
        member_count = len(self.members)
        if member_count != len(class_obj.members):
            return False

        for i in range(member_count):
            if self.members[i] != class_obj.members[i]:
                return False
        return True

    def __ne__(self, other: 'Any') -> bool:
        return not self.__eq__(other)


class Member(object):
    def __init__(self, index: int, name: str, bin_type: 'BinaryType', extra_type_info: 'ExtraInfoType') -> None:
        if not structs.ExtraTypeInfo.validate(bin_type, extra_type_info):
            raise exception.InvalidExtraInfoValue(extra_type_info, bin_type)

        self._index = int(index)
        self._name = str(name)
        self._binary_type = dotnet.enum.BinaryType(bin_type)
        self._extra_info = extra_type_info

    @property
    def name(self) -> str:
        return self._name

    @property
    def index(self) -> int:
        return self._index

    @property
    def binary_type(self) -> 'BinaryType':
        return self._binary_type

    @property
    def extra_info(self) -> 'ExtraInfoType':
        return self._extra_info

    def read(self, fp: 'BinaryIO', data_store: 'DataStore') -> 'Value':
        if self._binary_type == enums.BinaryType.Primitive:
            primitive_class = primitive.Primitive.get_class(self._extra_info)
            return primitive_class.read(fp)
        # If it isn't a primitivev, then read a record byte from the stream
        record_byte = fp.read(1)[0]
        record_type = enums.RecordType(record_byte)
        record_class = record.Record.get_class(record_type)
        record_instance = record_class.read(fp)
        if issubclass(record_class, record.ArrayRecord):
            # TODO: Read the array data from the stream
            pass
        elif issubclass(record_class, record.ClassRecord):
            class_record = record_instance  # type:ClassRecord
            class_object = data_store.build_class(class_record)
            class_instance = class_object.read_instance(fp, data_store, class_record.object_id)
            data_store.objects[class_instance.object_id] = class_instance
            return class_instance
        return record_instance

    def __eq__(self, other: 'Any') -> bool:
        if type(other) is not Member:
            return False

        member_obj = other  # type: Member
        return (member_obj.index == self.index and member_obj.name == self.name and
                member_obj.binary_type == self.binary_type and member_obj.extra_info == self.extra_info)

    def __ne__(self, other: 'Any') -> bool:
        return not self.__eq__(other)
