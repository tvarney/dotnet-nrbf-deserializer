
from abc import ABCMeta, abstractmethod

import dotnet.enum as enums
import dotnet.exceptions as exceptions
import dotnet.structures as structs
import dotnet.utils as utils
import dotnet.value

import typing
if typing.TYPE_CHECKING:
    from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
    from dotnet.enum import BinaryType, BinaryArrayType
    from dotnet.primitives import Primitive, PrimitiveValue
    from dotnet.structures import ExtraInfoType
    from dotnet.value import Value


class DataStore(object):
    _DefaultDataStore = None

    @staticmethod
    def get_global() -> 'DataStore':
        if DataStore._DefaultDataStore is None:
            DataStore._DefaultDataStore = DataStore()
        return DataStore._DefaultDataStore

    def __init__(self) -> None:
        self._next_lib_id = 1
        self._next_obj_id = 1

        self._libraries = {-1: Library.SystemLibrary}  # type: Dict[int, Library]
        self._classes = dict()  # type: Dict[Tuple[int, str], ClassObject]
        self._known_metadata = dict()  # type: Dict[Tuple[int, str], List[Member]]

    @property
    def libraries(self) -> 'Dict[int, Library]':
        return self._libraries

    @property
    def classes(self) -> 'Dict[Tuple[int, str], ClassObject]':
        return self._classes

    @property
    def metadata(self) -> 'Dict[Tuple[int, str], List[Member]]':
        return self._known_metadata

    def get_library_id(self) -> int:
        lib_id = self._next_lib_id
        self._next_lib_id += 1
        return lib_id

    def get_object_id(self) -> int:
        obj_id = self._next_obj_id
        self._next_obj_id += 1
        return obj_id


class Instance(dotnet.value.Value, metaclass=ABCMeta):
    def __init__(self, object_id: int) -> None:
        self._object_id = object_id

    @property
    def object_id(self) -> int:
        return self._object_id

    @object_id.setter
    def object_id(self, new_object_id: int) -> None:
        # TODO: Implement changing the object id within the data store
        if new_object_id == 0:
            raise ValueError("Can not set Instance object id to 0")
        self._object_id = new_object_id

    @abstractmethod
    def resolve_references(self, object_map: 'Dict[int, Instance]', strict: bool=True) -> None:
        raise exceptions.MethodNotImplemented(self, "resolve_references()")

    @abstractmethod
    def __getitem__(self, key: 'Any') -> 'Any':
        raise exceptions.MethodNotImplemented(self, "__getitem__()")

    @abstractmethod
    def __setitem__(self, key: 'Any', value: 'Any') -> None:
        raise exceptions.MethodNotImplemented(self, "__setitem__()")

    def __eq__(self, other: 'Any') -> bool:
        if issubclass(type(other), Instance):
            other: 'Instance'
            return self._object_id == other._object_id
        return False

    def __ne__(self, other: 'Any') -> bool:
        return not self.__eq__(other)


class ArrayInstance(Instance, metaclass=ABCMeta):
    def __init__(self, object_id: int, data: 'List[Any]') -> None:
        Instance.__init__(self, object_id)
        self._data = data

    @property
    def data(self) -> 'List[Any]':
        return self._data

    def resolve_references(self, object_map: 'Dict[int, Instance]', strict: bool=True) -> None:
        for i, value in enumerate(self._data):
            if type(value) is InstanceReference:
                ref = value  # type: InstanceReference
                if ref.object_id == 0:
                    self._data[i] = None
                else:
                    new_value = object_map.get(ref.object_id, None)
                    if new_value is None and strict:
                        raise exceptions.InvalidReferenceError()
                    self._data[i] = new_value

    def __str__(self) -> str:
        return "[{}]".format(", ".join(str(value) for value in self._data))


class InstanceReference(dotnet.value.Value):
    def __init__(self, object_id: int, object_map: 'Optional[Dict[int, Instance]]'=None) -> None:
        self._object_id = object_id
        self._object_map = object_map

    @property
    def object_id(self) -> int:
        return self._object_id

    @object_id.setter
    def object_id(self, new_object_id: int) -> None:
        self._object_id = new_object_id

    def resolve(self) -> 'Optional[Instance]':
        if self._object_id == 0:
            return None
        return self._object_map.get(self._object_id, None)

    def __call__(self) -> 'Instance':
        return self.resolve()

    def __getitem__(self, key: 'Any') -> 'Any':
        return self()[key]

    def __setitem__(self, key: 'Any', value: 'Any') -> None:
        self()[key] = value

    def __repr__(self) -> str:
        return "InstanceReference({})".format(self._object_id)

    def __str__(self) -> str:
        if self._object_id == 0:
            return "Null"
        return "Reference {}".format(hex(self._object_id))


class BinaryArray(ArrayInstance):
    def __init__(self, object_id: int, rank: int, array_type: 'BinaryArrayType', lengths: 'List[int]',
                 offsets: 'Optional[List[int]]', bin_type: 'BinaryType', extra_type_info: 'ExtraInfoType',
                 data: 'Optional[List[Optional[Value]]]') -> None:
        data_array = data if data is not None else list()
        ArrayInstance.__init__(self, object_id, data_array)
        self._rank = rank
        self._array_type = array_type
        self._lengths = lengths
        self._offsets = offsets
        self._bin_type = bin_type
        self._extra_info = extra_type_info
        self._default_value = None
        if self._bin_type == enums.BinaryType.Primitive:
            pass

    @property
    def rank(self) -> int:
        return self._rank

    @property
    def array_type(self) -> 'BinaryArrayType':
        return self._array_type

    @property
    def lengths(self) -> 'List[int]':
        return self._lengths

    @property
    def offsets(self) -> 'List[int]':
        return self._offsets

    @property
    def binary_type(self) -> 'BinaryType':
        return self._bin_type

    @property
    def extra_type_info(self) -> 'ExtraInfoType':
        return self._extra_info

    def __getitem__(self, key: int) -> 'Optional[Value]':
        return self._data[key]

    def __setitem__(self, key: int, value: 'Optional[Value]') -> None:
        self._data[key] = value


class ObjectArray(ArrayInstance):
    def __init__(self, object_id: int, data: 'List[Union[Instance, InstanceReference, None]]') -> None:
        ArrayInstance.__init__(self, object_id, data)

    def __getitem__(self, index: int) -> 'Any':
        return self._data[index]

    def __setitem__(self, index: int, value: 'Union[Instance, InstanceReference, None]') -> None:
        self._data[index].object_id = value.object_id


class StringArray(ArrayInstance):
    def __init__(self, object_id: int, data: 'List[str]') -> None:
        ArrayInstance.__init__(self, object_id, data)

    def __getitem__(self, index: int) -> str:
        return self._data[index]

    def __setitem__(self, index: int, value: str) -> None:
        self._data[index] = str(value)

    def __iter__(self) -> 'Iterator':
        for item in self._data:
            yield item


class PrimitiveArray(ArrayInstance):
    def __init__(self, object_id: int, primitive_class: type, data: 'List[Primitive]') -> None:
        ArrayInstance.__init__(self, object_id, data)
        self._data_class = primitive_class

    @property
    def primitive_class(self) -> type:
        return self._data_class

    def __getitem__(self, index: int) -> 'Primitive':
        return self._data[index]

    def __setitem__(self, index: int, new_data: 'PrimitiveValue') -> None:
        self._data[index].value = utils.move(new_data, self._data_class)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):
        for value in self._data:
            yield value


class ClassInstance(Instance):
    def __init__(self, object_id: int, class_object: 'ClassObject', member_data: 'List[Value]') -> None:
        Instance.__init__(self, object_id)
        self._class_object = class_object
        self._member_data = member_data

    @property
    def class_object(self) -> 'ClassObject':
        return self._class_object

    @property
    def member_data(self) -> 'List[Value]':
        return self._member_data

    def resolve_references(self, object_map: 'Dict[int, Instance]', strict: bool=True) -> None:
        for i, member_data in enumerate(self._member_data):
            if type(member_data) is InstanceReference:
                ref = member_data  # type: InstanceReference
                new_value = object_map.get(ref.object_id, None)
                if new_value is None and strict:
                    raise exceptions.InvalidReferenceError()
                self._member_data[i] = new_value

    def __getitem__(self, key: 'Union[int, str]') -> 'Value':
        if type(key) is int:
            return self._member_data[key]
        member_idx = self._class_object.get_member(key).index
        return self._member_data[member_idx]

    def __setitem__(self, key: 'Union[int, str]', value: 'Value') -> None:
        if type(key) is str:
            key = self._class_object.get_member(key).index
        self._member_data[key] = value


class Library(object):
    NoId = -1

    @staticmethod
    def parse_string(str_value: str) -> 'Library':
        parts = str_value.split(",")
        name = parts[0].strip()
        options = dict()  # type: Dict[str, str]
        for i in range(1, len(parts)):
            opt_parts = parts[i].split("=", 1)
            if len(opt_parts) == 2:
                options[opt_parts[0].strip()] = opt_parts[1].strip()
            else:
                raise ValueError("Failed to parse library options")
        return Library(name, **options)

    def __init__(self, name, **options) -> None:
        self._name = name
        self._system = bool(options.pop("system", False))
        self._options = options
        self._library_id = options.pop("library_id", -1)
        # TODO: Validate the library id (may truncate)

    @property
    def name(self) -> str:
        return self._name

    @property
    def system(self) -> bool:
        return self._system

    @property
    def options(self) -> 'Dict[str, str]':
        return self._options

    @property
    def id(self) -> int:
        return self._library_id

    @id.setter
    def id(self, new_id: int) -> None:
        if self._library_id != -1:
            raise RuntimeError("Can not set the library id multiple times")
        self._library_id = new_id

    def __getitem__(self, key: str) -> str:
        return self._options[key]

    def __str__(self) -> str:
        return "[{}]".format(
            self._name + ', '.join("{}={}".format(key, value) for key, value in self._options.items())
        )

    def __repr__(self) -> str:
        return "Library({})".format(
            self._name + ', '.join("{}={}".format(key, repr(value)) for key, value in self._options.items())
        )


Library.SystemLibrary = Library("System", system=True, library_id=-1)


class ClassObject(object):
    SystemClass = -1

    def __init__(self, name: str, members: 'List[Member]', partial: bool, library: 'Library',
                 data_store: 'Optional[DataStore]'=None) -> None:
        """Create a new Class object

        :param name: The name of the class
        :param members: The data members of the object
        :param partial: If the class should be written without types
        :param library: The resolved library for this class
        :param data_store: The DataStore holding this class
        """
        self._name = str(name)
        self._members = members
        self._partial = bool(partial)
        self._library = library
        self._data_store = data_store if data_store is not None else DataStore.get_global()
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
    def library(self) -> 'Library':
        return self._library

    @property
    def library_id(self) -> int:
        return self._library.id

    @property
    def partial(self) -> bool:
        return self._partial

    @property
    def key(self) -> 'Tuple[int, str]':
        return self._library.id, self._name

    def get_member(self, member_name: str) -> 'Member':
        return self._lookup[member_name]

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
        structs.ExtraTypeInfo.check(bin_type, extra_type_info)

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

    def __eq__(self, other: 'Any') -> bool:
        if type(other) is not Member:
            return False

        member_obj = other  # type: Member
        return (member_obj.index == self.index and member_obj.name == self.name and
                member_obj.binary_type == self.binary_type and member_obj.extra_info == self.extra_info)

    def __ne__(self, other: 'Any') -> bool:
        return not self.__eq__(other)
