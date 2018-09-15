
from abc import ABCMeta

import nrbf.enum
from nrbf.value import Value

import typing
if typing.TYPE_CHECKING:
    from typing import BinaryIO, Dict, List, Tuple, Union
    from nrbf.enum import BinaryType, PrimitiveType

    InfoType = Union[None, str, PrimitiveType]


class DataStore(object):
    def __init__(self) -> None:
        self._libraries = {-1: "System"}  # type: Dict[int, str]
        self._objects = dict()  # type: Dict[int, Instance]
        self._classes = dict()  # type: Dict[Tuple[int, str], ClassObject]
        self._known_metadata = dict()  # type: Dict[Tuple[str, str], object]


class Instance(Value, metaclass=ABCMeta):
    def __init__(self, object_id: int) -> None:
        self._object_id = object_id

    @property
    def object_id(self) -> int:
        return self._object_id


class ArrayInstance(Instance, metaclass=ABCMeta):
    def __init__(self, object_id: int) -> None:
        Instance.__init__(self, object_id)


class ClassObject(Value):
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
        self._written = False
        for member in self._members:
            self._lookup[member.index] = member

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

    @property
    def written(self) -> bool:
        return self._written

    @written.setter
    def written(self, new_value: bool) -> None:
        self._written = bool(new_value)

    def write(self, fp: 'BinaryIO'):
        fp.write(bytes(self))

    def __bytes__(self) -> bytes:
        return b''


class Member(object):
    def __init__(self, index: int, name: str, bin_type: 'BinaryType', additional_info: 'InfoType') -> None:
        self._index = int(index)
        self._name = str(name)
        self._binary_type = nrbf.enum.BinaryType(bin_type)
        self._additional_info = additional_info

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
    def info(self) -> 'InfoType':
        return self._additional_info

    def read(self, fp: 'BinaryIO', data_store: 'DataStore') -> Value:
        raise NotImplementedError()
