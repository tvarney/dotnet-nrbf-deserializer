
import dotnet.enum as enums
import dotnet.exceptions as exception
import dotnet.primitives as primitive
import dotnet.structures as structs
import dotnet.utils as utils
import dotnet.value

import typing
if typing.TYPE_CHECKING:
    from typing import Any, Dict, List, Tuple, Union
    from dotnet.enum import BinaryType
    from dotnet.primitives import Int32, Int32Value, Primitive, PrimitiveValue
    from dotnet.structures import ExtraInfoType
    from dotnet.value import Value


class DataStore(object):
    def __init__(self) -> None:
        self._next_lib_id = 1
        self._next_obj_id = 1
        self._null = InstanceReference(0, self)

        self._libraries = {-1: Library.SystemLibrary}  # type: Dict[int, Library]
        self._objects = dict()  # type: Dict[int, Instance]
        self._classes = dict()  # type: Dict[Tuple[int, str], ClassObject]
        self._known_metadata = dict()  # type: Dict[Tuple[int, str], List[Member]]

        self._objects[0] = self._null

    @property
    def libraries(self) -> 'Dict[int, Library]':
        return self._libraries

    @property
    def objects(self) -> 'Dict[int, Instance]':
        return self._objects

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


class Instance(dotnet.value.Value):
    def __init__(self, object_id: 'Int32Value') -> None:
        self._object_id = utils.move(object_id, primitive.Int32)  # type: Int32

    @property
    def object_id(self) -> int:
        return self._object_id.value

    @object_id.setter
    def object_id(self, new_object_id: 'Int32Value') -> None:
        self._object_id.value = new_object_id


class ArrayInstance(Instance):
    pass


class InstanceReference(Instance):
    def __init__(self, object_id: 'Int32Value', data_store: 'DataStore') -> None:
        Instance.__init__(self, object_id)
        self._data_store = data_store

    def data_store(self) -> 'DataStore':
        pass

    def resolve(self) -> 'Instance':
        return self._data_store.objects[self._object_id.value]


class ObjectArray(ArrayInstance):
    def __init__(self, object_id: 'Int32Value', data: 'List[Any]'):
        ArrayInstance.__init__(self, object_id)
        self._data = data

    def __getitem__(self, index: int) -> 'Any':
        return self._data[index]


class StringArray(ArrayInstance):
    def __init__(self, object_id: 'Int32Value', data: 'List[Any]'):
        ArrayInstance.__init__(self, object_id)
        self._data = data


class PrimitiveArray(ArrayInstance):
    def __init__(self, object_id: 'Int32Value', primitive_class: type, data: 'List[Primitive]') -> None:
        ArrayInstance.__init__(self, object_id)
        self._data_class = primitive_class
        self._data = data

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


class ClassObject(dotnet.value.Value):
    SystemClass = -1

    def __init__(self, name: str, members: 'List[Member]', partial: bool, library: 'Library',
                 data_store: 'DataStore') -> None:
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
        self._data_store = data_store
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

    def __eq__(self, other: 'Any') -> bool:
        if type(other) is not Member:
            return False

        member_obj = other  # type: Member
        return (member_obj.index == self.index and member_obj.name == self.name and
                member_obj.binary_type == self.binary_type and member_obj.extra_info == self.extra_info)

    def __ne__(self, other: 'Any') -> bool:
        return not self.__eq__(other)
