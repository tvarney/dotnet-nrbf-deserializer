
from abc import ABCMeta, abstractmethod
import io

import dotnet.enum as enums
import dotnet.exceptions as exceptions
import dotnet.primitives as primitives
import dotnet.structures as structs
import dotnet.utils as utils
import dotnet.value

import typing
if typing.TYPE_CHECKING:
    from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Union
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
        self._libraries = {hash(Library.SystemLibrary): Library.SystemLibrary}  # type: Dict[int, Library]
        self._classes = dict()  # type: Dict[Tuple[Library, str], ClassObject]
        self._known_metadata = dict()  # type: Dict[Tuple[Library, str], List[Member]]

    @property
    def libraries(self) -> 'Dict[int, Library]':
        return self._libraries

    @property
    def classes(self) -> 'Dict[Tuple[Library, str], ClassObject]':
        return self._classes

    @property
    def metadata(self) -> 'Dict[Tuple[Library, str], List[Member]]':
        return self._known_metadata


class Instance(dotnet.value.Value, metaclass=ABCMeta):
    def __init__(self, data_store: 'Optional[DataStore]'=None) -> None:
        self._data_store = data_store if data_store is not None else DataStore.get_global()

    @property
    def data_store(self) -> 'DataStore':
        return self._data_store

    @abstractmethod
    def resolve_references(self, object_map: 'Dict[int, Instance]', strict: bool=True) -> None:
        raise exceptions.MethodNotImplemented(self, "resolve_references()")

    def __repr__(self) -> str:
        return "Instance({})".format(self._object_id)

    def __str__(self) -> str:
        return "<Instance: {}>".format(self._object_id)

    @abstractmethod
    def __getitem__(self, key: 'Any') -> 'Any':
        raise exceptions.MethodNotImplemented(self, "__getitem__()")

    @abstractmethod
    def __setitem__(self, key: 'Any', value: 'Any') -> None:
        raise exceptions.MethodNotImplemented(self, "__setitem__()")

    def __eq__(self, other: 'Any') -> bool:
        return id(self) == id(other)

    def __ne__(self, other: 'Any') -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return id(self)


class ArrayInstance(Instance, metaclass=ABCMeta):
    def __init__(self, data: 'List[Any]', data_store: 'Optional[DataStore]'=None) -> None:
        Instance.__init__(self, data_store)
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

    def __repr__(self) -> str:
        return "{}({})".format(type(self).__name__, self._data)

    def __len__(self) -> int:
        return len(self._data)


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
    def __init__(self, rank: int, array_type: 'BinaryArrayType', lengths: 'List[int]', offsets: 'Optional[List[int]]',
                 bin_type: 'BinaryType', extra_type_info: 'ExtraInfoType', data: 'Optional[List[Optional[Value]]]',
                 data_store: 'Optional[DataStore]'=None) -> None:
        data_array = data if data is not None else list()
        ArrayInstance.__init__(self, data_array, data_store)
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

    def __repr__(self) -> str:
        return "BinaryArray({}, {}, {}, {}, {}, {}, {})".format(
            self._rank, self._array_type, self._lengths, self._offsets, self._bin_type,
            self._extra_info, self._data
        )


class ObjectArray(ArrayInstance):
    def __init__(self, data: 'List[Union[Instance, InstanceReference, None]]',
                 data_store: 'Optional[DataStore]'=None) -> None:
        ArrayInstance.__init__(self, data, data_store)

    def get_libraries(self) -> 'Set[Library]':
        libs = set()
        for item in self._data:
            if issubclass(type(item), ClassInstance):
                class_obj = item.class_object  # type: ClassObject
                libs.add(class_obj.library)

        return libs

    def is_value_type_array(self) -> bool:
        if len(self._data) == 0:
            return True

        first_item = self._data[0]
        if first_item is None:
            return False

        # Check for ClassInstance
        if issubclass(first_item, ClassInstance):
            data_class = first_item.class_object  # type: ClassObject
            if not data_class.value_type:
                return False

            for item in self._data:
                if issubclass(item, ClassInstance):
                    if item.class_object != data_class:
                        return False
                else:
                    return False
            return True

        return False

    def __getitem__(self, index: int) -> 'Any':
        return self._data[index]

    def __setitem__(self, index: int, value: 'Union[Instance, InstanceReference, None]') -> None:
        self._data[index].object_id = value.object_id


class StringArray(ArrayInstance):
    def __init__(self, data: 'List[Optional[str]]', data_store: 'Optional[DataStore]'=None) -> None:
        ArrayInstance.__init__(self, data, data_store)

    def __getitem__(self, index: int) -> 'Optional[str]':
        return self._data[index]

    def __setitem__(self, index: int, value: 'Optional[str]') -> None:
        self._data[index] = value

    def __iter__(self) -> 'Iterator':
        for item in self._data:
            yield item


class PrimitiveArray(ArrayInstance):
    def __init__(self, primitive_class: type, data: 'List[Primitive]', data_store: 'Optional[DataStore]'=None) -> None:
        ArrayInstance.__init__(self, data, data_store)
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

    def __repr__(self) -> str:
        return "PrimitiveArray({}, {})".format(self._data_class, self._data)


class ClassInstance(Instance):
    def __init__(self, class_object: 'ClassObject', member_data: 'List[Value]',
                 data_store: 'Optional[DataStore]'=None) -> None:
        Instance.__init__(self, data_store)
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

    def __repr__(self) -> str:
        return "ClassInstance({}, {})".format(repr(self._class_object), repr(self._member_data))

    def __str__(self) -> str:
        return "<{} Instance: {}>".format(self._class_object.name, id(self))


class StringInstance(Instance):
    def __init__(self, str_data: str, data_store: 'Optional[DataStore]'=None) -> None:
        Instance.__init__(self, data_store)
        self._data = str_data

    @property
    def value(self) -> str:
        return self._data

    @value.setter
    def value(self, new_str_value: str) -> None:
        self._data = str(new_str_value)

    def resolve_references(self, object_map: 'Dict[int, Instance]', strict: bool=True) -> None:
        pass

    def __str__(self) -> str:
        return self._data

    def __repr__(self) -> str:
        return "StringInstance({})".format(self._data)

    def __eq__(self, other: 'Any') -> bool:
        value_type = type(other)
        if value_type is str or value_type is primitives.String or value_type is StringInstance:
            return str(other) == self._data
        return False

    def __getitem__(self, key: 'Any') -> str:
        if key == 0 or key == 'data':
            return self._data
        raise KeyError("Invalid key {} on String Instance".format(key))

    def __setitem__(self, key: 'Any', value: str) -> None:
        if key == 0 or key == 'data':
            self._data = str(value)
        else:
            raise KeyError("Invalid key {} on String Instance".format(key))

    def __hash__(self) -> int:
        return hash(self._data)


class Library(object):
    SystemLibrary = None

    @staticmethod
    def parse_specification(spec_string: str, system: bool=False) -> 'Library':
        """Initialize a library from the given specification string

        The format of a library specification string is given in MS-NRTP
        2.2.1.3 LibraryName.

        The library name format is defined as follows:
          LibraryName: LibraryIdentifier (',' LibraryProperty)*
          LibraryIdentifier: IDENTIFIER
          LibraryProperty: VersionProperty | PublicKeyTokenProperty |
                           CultureProperty | RetargetableProperty
          CultureProperty: 'Culture=' [alpha]{1,8}('-' [alpha]{1,8})*
          PublicKeyTokenProperty: 'PublicKeyToken=' TokenValue
          RetargetableProperty: 'Retargetable=' ('Yes'|'No')
          VersionProperty: 'Version=' VersionValue
          VersionValue: uint16 '.' uint16 '.' uint16 '.' uint16
          uint16: [digit]{1,5}
          TokenValue: [hexdigit]{16,16} | 'null'

        This means that a specification string may contain the following
        options:
          * Culture
          * PublicKeyToken
          * Retargetable
          * Version
        All values, if not present, are given the empty string as their
        value.

        At present, the only values which are used for equality and
        hashing are the name and version of the library.

        :param spec_string:
        :param system:
        """
        parts = spec_string.split(',')
        name = parts[0].strip()
        options = dict()
        for i in range(1, len(parts)):
            opt_parts = parts[i].split("=", 1)
            if len(opt_parts) != 2:
                raise ValueError("Failed to parse library specification string")
            options[opt_parts[0].strip()] = opt_parts[1].strip()

        version = options.pop('Version', '')
        retargetable = options.pop('Retargetable', '')
        public_key = options.pop('PublicKeyToken', '')
        culture = options.pop('Culture', '')

        if len(options.keys()) > 0:
            raise ValueError("Unrecognized options in spec string: {}".format(
                ', '.join(options.keys())
            ))

        return Library(name, system=system, version=version, retargetable=retargetable, culture=culture,
                       public_key=public_key)

    def __init__(self, name: str, version: str='', system: bool=False, retargetable: 'Union[str, bool]'='',
                 culture: str='', public_key: str='') -> None:
        self._name = name
        self._version = version
        self._system = system
        self._retargetable = retargetable
        if type(retargetable) is bool:
            self._retargetable = 'Yes' if retargetable else 'No'
        self._culture = culture
        self._public_key = public_key
        self._spec = ''

        self._validate()

    @property
    def culture(self) -> str:
        return self._culture

    @culture.setter
    def culture(self, new_value: 'Optional[str]') -> None:
        value = '' if new_value is None else str(new_value)
        if value != '':
            parts = value.split('-')
            for part in parts:
                len_part = len(part)
                if len_part < 1 or len_part > 8 or not part.isalpha():
                    raise ValueError("Invalid Culture format")

        if value != self._culture:
            self._spec = ''
        self._culture = value

    @property
    def name(self) -> str:
        return self._name

    @property
    def public_key(self) -> str:
        return self._public_key

    @public_key.setter
    def public_key(self, new_value: 'Optional[str]') -> None:
        value = '' if new_value is None else str(new_value)

        if value != '':
            # Validate the public key
            _ = int(value, 16)

        if value != self._public_key:
            self._spec = ''
        self._public_key = value

    @property
    def retargetable(self) -> str:
        return self._retargetable

    @retargetable.setter
    def retargetable(self, new_value: 'Union[bool, str, None]') -> None:
        value_type = type(new_value)
        if value_type is bool:
            new_value = 'Yes' if new_value else 'No'
            value_type = str
        elif new_value is None:
            new_value = ''
            value_type = str

        if value_type is str:
            if new_value not in ('', 'Yes', 'No'):
                raise ValueError("Retargetable property requires one of '', 'Yes', or 'No'")
            if new_value != self._retargetable:
                self._spec = ''
            self._retargetable = new_value
        else:
            raise TypeError("Retargetable property expects one of str, bool, or None")

    @property
    def spec(self) -> str:
        if self._spec == '':
            self._spec = self._get_str()
        return self._spec

    @property
    def system(self) -> bool:
        return self._system

    @property
    def version(self) -> str:
        return self._version

    def __eq__(self, other: 'Any') -> bool:
        if type(other) is Library:
            return self.name == other.name and self.version == other.version
        return False

    def __ne__(self, other: 'Any') -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.name, self.version))

    def __str__(self) -> str:
        return self.spec

    def __repr__(self) -> str:
        if self.system:
            return "Library({}, system=True)".format(self.spec)
        return "Library({})".format(self.spec)

    def _validate(self) -> None:
        if self._version != '':
            version_parts = self._version.split('.')
            if len(version_parts) != 4:
                raise ValueError("Invalid Version format")
            for part in version_parts:
                part_val = int(part)
                if part_val < 0 or part_val >= 65536:
                    raise ValueError('Invalid Version value')

        if self._retargetable not in ('', 'Yes', 'No'):
            raise ValueError("Invalid Retargetable value; must be one of '', 'Yes', or 'No'")

        if self._culture != '':
            culture_parts = self._culture.split('-')
            for part in culture_parts:
                len_part = len(part)
                if len_part < 1 or len_part > 8 or not part.isalpha():
                    raise ValueError("Invalid Culture format")

        if self._public_key != '' and self._public_key != 'null':
            _ = int(self._public_key, 16)

    def _get_str(self) -> str:
        sb = io.StringIO()
        sb.write(self._name)
        if self._version != '':
            sb.write(', Version=')
            sb.write(self._version)
        if self._culture != '':
            sb.write(', Culture=')
            sb.write(self._culture)
        if self._public_key != '':
            sb.write(', PublicKeyToken=')
            sb.write(self._public_key)
        if self._retargetable != '':
            sb.write(', Retargetable=')
            sb.write(self._retargetable)
        return sb.getvalue()


Library.SystemLibrary = Library("System", system=True)


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
        self._value_type = False
        self._data_store = data_store if data_store is not None else DataStore.get_global()
        self._lookup = dict()  # type: Dict[str, Member]
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
    def partial(self) -> bool:
        return self._partial

    @property
    def value_type(self) -> bool:
        return self._value_type

    @value_type.setter
    def value_type(self, is_value_type: bool) -> None:
        self._value_type = bool(is_value_type)

    @property
    def key(self) -> 'Tuple[Library, str]':
        return self._library, self._name

    @property
    def record_type(self) -> 'enums.RecordType':
        if self.library.system:
            if self.partial:
                return enums.RecordType.SystemClassWithMembers
            return enums.RecordType.SystemClassWithMembersAndTypes
        if self.partial:
            return enums.RecordType.ClassWithMembers
        return enums.RecordType.ClassWithMembersAndTypes

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

    def __repr__(self) -> str:
        return "ClassObject({}, {}, {}, {}, {})".format(
            repr(self._name), repr(self._members), repr(self._partial),
            repr(self._library), repr(self._data_store)
        )

    def __str__(self) -> str:
        return "<Class: {}, {}>".format(self._name, str(self._library))


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

    def __repr__(self) -> str:
        return "Member({}, {}, BinaryType.{}, {})".format(
            self._index, repr(self._name), self._binary_type.name,
            structs.ExtraTypeInfo.inspect(self._binary_type, self._extra_info)
        )

    def __str__(self) -> str:
        return self.__repr__()
