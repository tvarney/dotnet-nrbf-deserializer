
import abc
import io

import nrbf.enum as enums
import nrbf.exceptions as exception
import nrbf.primitives as primitive
import nrbf.record as record
import nrbf.structures as structs
import nrbf.utils as utils
import nrbf.value

import typing
if typing.TYPE_CHECKING:
    from typing import BinaryIO, Dict, List, Tuple, Union
    from nrbf.enum import BinaryType
    from nrbf.primitives import Int32, Int32Value
    from nrbf.record import ClassRecord, Record
    from nrbf.structures import ExtraInfoType
    from nrbf.value import Value


class DataStore(object):
    def __init__(self) -> None:
        self._records = list()  # type: List[Record]
        self._libraries = {-1: "System"}  # type: Dict[int, str]
        self._objects = dict()  # type: Dict[int, Instance]
        self._classes = dict()  # type: Dict[Tuple[int, str], ClassObject]
        self._known_metadata = dict()  # type: Dict[Tuple[str, str], object]

    def read_file(self, filename: str, clear_records: bool=True) -> int:
        with open(filename, 'rb') as fp:
            return self.read_stream(fp, clear_records)

    def _build_class(self, class_record: 'ClassRecord') -> 'ClassObject':
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
            pass
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
                class_object = self._build_class(record_instance)

        return records_read


class Instance(nrbf.value.Value, metaclass=abc.ABCMeta):
    def __init__(self, object_id: 'Int32Value') -> None:
        self._object_id = utils.move(object_id, primitive.Int32)  # type: Int32

    @property
    def object_id(self) -> int:
        return self._object_id.value

    @object_id.setter
    def object_id(self, new_object_id: 'Int32Value') -> None:
        self._object_id.value = new_object_id


class ArrayInstance(Instance, metaclass=abc.ABCMeta):
    def __init__(self, object_id: 'Int32Value') -> None:
        Instance.__init__(self, object_id)


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

    def __getitem__(self, key: 'Union[int, str]') -> Value:
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


class ClassObject(nrbf.value.Value):
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

    def write(self, fp: 'BinaryIO'):
        fp.write(bytes(self))

    def __bytes__(self) -> bytes:
        return b''


class Member(object):
    def __init__(self, index: int, name: str, bin_type: 'BinaryType', extra_type_info: 'ExtraInfoType') -> None:
        if not structs.ExtraTypeInfo.validate(bin_type, extra_type_info):
            raise exception.InvalidExtraInfoValue(extra_type_info, bin_type)

        self._index = int(index)
        self._name = str(name)
        self._binary_type = nrbf.enum.BinaryType(bin_type)
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
        raise NotImplementedError()
