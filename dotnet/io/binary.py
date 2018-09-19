
import dotnet.enum as enums
import dotnet.io.base as base
import dotnet.primitives as primitives
import dotnet.object as objects
import dotnet.structures as structs
import dotnet.utils as utils

import typing
if typing.TYPE_CHECKING:
    from typing import BinaryIO, Dict, List, Optional, Tuple, Type

    from dotnet.enum import PrimitiveType
    from dotnet.object import ClassObject, ClassInstance, DataStore, Instance, Library, PrimitiveArray, \
        ObjectArray, StringArray
    from dotnet.primitives import Char, Decimal, Primitive, String
    from dotnet.structures import ClassInfo, MemberTypeInfo


class BinaryFormatter(base.Formatter):
    class ReadState(object):
        def __init__(self) -> None:
            self.root_id = 0
            self.header_id = 0
            self.major_version = 0
            self.minor_version = 0
            self.objects = dict()  # type: Dict[int, Instance]
            self.libraries = dict()  # type: Dict[int, Library]
            self.object_id_map = dict()  # type: Dict[int, int]
            self.library_id_map = dict()  # type: Dict[int, int]
            self.references = list()

    @classmethod
    def binary(cls) -> bool:
        return True

    def __init__(self, data_store: 'Optional[DataStore]'=None, **kwargs) -> None:
        if data_store is None:
            ds = objects.DataStore()
        else:
            ds = data_store
        self._data_store = ds
        self._state = BinaryFormatter.ReadState()
        self._strict = not bool(kwargs.pop("permissive", False))
        self._read_record_fn = [
            self.read_header,
            self.read_class_with_id,
            self.read_system_class_partial,
            self.read_class_partial,
            self.read_system_class_full,
            self.read_class_full,
            self.read_string,
            self.read_binary_array,
            self.read_primitive,
            self.read_reference,
            self.read_null,
            None,
            self.read_library,
            self.read_null_multiple_256,
            self.read_null_multiple,
            self.read_primitive_array,
            self.read_object_array,
            self.read_string_array,
            None,
            None,
            None,
            None,
            None
        ]

    def _get_obj_id(self, state_obj_id: int) -> int:
        if state_obj_id in self._state.object_id_map:
            raise KeyError("Duplicate ObjectID in stream")
        object_id = self._data_store.get_object_id()
        self._state.object_id_map[state_obj_id] = object_id
        return object_id

    def build_class(self, class_info: 'ClassInfo', library: 'Library',
                    member_info: 'Optional[MemberTypeInfo]') -> 'ClassObject':
        if member_info is None:
            partial = True
            members = self._data_store.metadata.get((library.id, class_info.name.value), None)
        else:
            partial = False
            member_count = len(class_info.members)
            if member_count != len(member_info.binary_types):
                raise ValueError("Mismatch between members names and member type info")

            members = list()  # type: List[objects.Member]
            for i in range(member_count):
                members.append(objects.Member(
                    i, class_info.members[i].value, member_info.binary_types[i], member_info.extra_info[i]
                ))

        class_obj = objects.ClassObject(class_info.name.value, members, partial, library, self._data_store)
        old_class_obj = self._data_store.classes.get(class_obj.key, None)
        if old_class_obj is None:
            self._data_store.classes[class_obj.key] = class_obj
            return class_obj
        else:
            if old_class_obj != class_obj:
                raise ValueError("Non-duplicate classes of same name in same library")
            return old_class_obj

    def read(self, fp: 'BinaryIO') -> 'Instance':
        self.read_header(fp, True)
        while self.read_record(fp):
            pass

        return self._state.objects[self._state.root_id]

    def read_binary_array(self, fp: 'BinaryIO') -> 'Instance':
        pass

    @staticmethod
    def read_char(fp: 'BinaryIO') -> 'Char':
        bytes_value = fp.read(1)
        first_byte = bytes_value[0]
        if first_byte > 127:
            if first_byte >= 0xF0:
                return primitives.Char(bytes_value + fp.read(3))
            if first_byte >= 0xE0:
                return primitives.Char(bytes_value + fp.read(2))
            return primitives.Char(bytes_value + fp.read(1))
        return primitives.Char(bytes_value)

    def read_class_instance(self, fp: 'BinaryIO', obj_id: int, class_obj: 'ClassObject') -> 'ClassInstance':
        data = list()
        null_count = 0
        for member in class_obj.members:
            if null_count > 0:
                data.append(None)
                null_count -= 1
            elif member.binary_type == enums.BinaryType.Primitive:
                data.append(self.read_primitive_type(fp, member.extra_info))
            else:
                record_byte = fp.read(1)[0]
                record_type = enums.RecordType(record_byte)
                if record_type == enums.RecordType.ObjectNullMultiple:
                    null_count = int.from_bytes(fp.read(4), 'little', signed=True) - 1
                    data.append(objects.InstanceReference(0, self._data_store))
                elif record_type == enums.RecordType.ObjectNullMultiple256:
                    null_count = fp.read(1)[0] - 1
                    data.append(None)
                elif record_type == enums.RecordType.ObjectNull:
                    data.append(None)
                else:
                    read_fn = self._read_record_fn[record_type]
                    value = read_fn(fp)
                    if value is None:
                        raise ValueError("Member expected value, got nothing")
                    data.append(value)
        class_inst = objects.ClassInstance(obj_id, class_obj, data)

        return class_inst

    def read_class_with_id(self, fp: 'BinaryIO') -> 'ClassInstance':
        object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        metadata_id = int.from_bytes(fp.read(4), 'little', signed=True)
        metadata_obj = self._state.objects[metadata_id]
        if type(metadata_obj) is objects.ClassInstance:
            class_inst = metadata_obj  # type: ClassInstance
            class_obj = class_inst.class_object
            return self.read_class_instance(fp, object_id, class_obj)
        raise ValueError("ClassWithId references non-class instance for metadata")

    def read_class_full(self, fp: 'BinaryIO') -> 'ClassInstance':
        class_info = structs.ClassInfo.read(fp)
        member_type_info = structs.MemberTypeInfo.read(fp, len(class_info.members))
        state_library_id = int.from_bytes(fp.read(4), 'little', signed=True)
        library = self._state.libraries[state_library_id]
        class_obj = self.build_class(class_info, library, member_type_info)
        return self.read_class_instance(fp, class_info.object_id.value, class_obj)

    def read_class_partial(self, fp: 'BinaryIO') -> 'ClassInstance':
        class_info = structs.ClassInfo.read(fp)
        library_id = int.from_bytes(fp.read(4), 'little', signed=True)
        library = self._state.libraries[library_id]
        class_obj = self.build_class(class_info, library, None)
        return self.read_class_instance(fp, class_info.object_id.value, class_obj)

    def read_decimal(self, fp: 'BinaryIO') -> 'Decimal':
        length = utils.read_multi_byte_int(fp)
        if length < 0:
            if self._strict:
                raise ValueError("Negative length while reading decimal")
            length = 0
        return primitives.Decimal(fp.read(length).decode('utf-8'))

    def read_header(self, fp: 'BinaryIO', read_record_type: bool=True) -> 'Tuple[int, int, int, int]':
        if read_record_type:
            header_byte = fp.read(1)[0]
            if header_byte != 0:
                raise IOError("Expected SerializedStreamHeader as first record")

        root_id = int.from_bytes(fp.read(4), 'little', signed=True)
        header_id = int.from_bytes(fp.read(4), 'little', signed=True)
        major = int.from_bytes(fp.read(4), 'little', signed=True)
        minor = int.from_bytes(fp.read(4), 'little', signed=True)

        if self._strict:
            if major != 1 or minor != 0:
                raise IOError("Invalid SerializedStreamHeader version {}.{}; must be 1.0".format(major, minor))

        self._state.minor_version = minor
        self._state.major_version = major
        self._state.root_id = root_id
        self._state.header_id = header_id
        return root_id, header_id, major, minor

    def read_library(self, fp: 'BinaryIO') -> 'Library':
        state_lib_id = int.from_bytes(fp.read(4), 'little', signed=True)
        str_value = self.read_string(fp)
        # TODO: check if we have a library which matches this one already
        library = objects.Library.parse_string(str_value.value)
        library.id = self._data_store.get_library_id()
        self._state.library_id_map[state_lib_id] = library.id
        self._state.libraries[state_lib_id] = library
        return library

    def read_null(self, fp: 'BinaryIO') -> None:
        return None

    def read_null_multiple(self, fp: 'BinaryIO') -> 'List[None]':
        count = int.from_bytes(fp.read(4), 'little', signed=True)
        return [None] * count

    def read_null_multiple_256(self, fp: 'BinaryIO') -> 'List[None]':
        count = fp.read(1)[0]
        return [None] * count

    def read_object_array(self, fp: 'BinaryIO') -> 'ObjectArray':
        state_object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        length = int.from_bytes(fp.read(4), 'little', signed=True)
        if length < 0:
            if self._strict:
                raise ValueError("Invalid array length while reading array")
            length = 0

        data = list()
        count = 0
        while count < length:
            record_byte = fp.read(1)[0]
            record_type = enums.RecordType(record_byte)
            if record_type == enums.RecordType.ObjectNullMultiple256:
                null_count = fp.read(1)[0]
                for _ in range(null_count):
                    data.append(None)
                count += null_count
            elif record_type == enums.RecordType.ObjectNullMultiple:
                null_count = int.from_bytes(fp.read(4), 'little', signed=True)
                for _ in range(null_count):
                    data.append(None)
                count += null_count
            else:
                read_fn = self._read_record_fn[record_type]
                data.append(read_fn(fp))

        object_id = self._data_store.get_object_id()
        array = objects.ObjectArray(object_id, data)
        self._state.objects[state_object_id] = array
        self._data_store.objects[object_id] = array
        return array

    def read_primitive(self, fp: 'BinaryIO') -> 'Primitive':
        primitive_type_byte = fp.read(1)[0]
        primitive_type = enums.PrimitiveType(primitive_type_byte)
        return self.read_primitive_type(fp, primitive_type)

    def read_primitive_array(self, fp: 'BinaryIO') -> 'PrimitiveArray':
        state_object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        if state_object_id in self._state.object_id_map.keys():
            raise KeyError("Duplicate object id in stream")

        length = int.from_bytes(fp.read(4), 'little', signed=True)
        if length < 0:
            if self._strict:
                raise ValueError("Invalid array length while reading array")
            length = 0

        type_byte = fp.read(1)[0]
        type_enum = enums.PrimitiveType(type_byte)
        type_class = primitives.Primitive.get_class(type_enum)
        value_size = type_class.byte_size()
        values = list()
        for _ in range(length):
            values.append(type_class(fp.read(value_size)))

        object_id = self._data_store.get_object_id()
        array = objects.PrimitiveArray(object_id, type_class, values)
        return array

    def read_primitive_class(self, fp: 'BinaryIO', primitive_class: 'Type[Primitive]') -> 'Primitive':
        size = primitive_class.byte_size()
        if size <= 0:
            primitive_type = type(primitive_class)
            if primitive_type is primitives.Char:
                return self.read_char(fp)
            if primitive_type is primitives.Decimal:
                return self.read_decimal(fp)
            if primitive_type is primitives.String:
                return self.read_string(fp)
            raise TypeError()
        byte_value = fp.read(size)
        return utils.move(byte_value, primitive_class)

    def read_primitive_type(self, fp: 'BinaryIO', primitive_type: 'PrimitiveType') -> 'Primitive':
        primitive_class = primitives.Primitive.get_class(primitive_type)
        size = primitive_class.byte_size()
        if size <= 0:
            if primitive_type == enums.PrimitiveType.Char:
                return self.read_char(fp)
            if primitive_type == enums.PrimitiveType.String:
                return self.read_string(fp)
            if primitive_type == enums.PrimitiveType.Decimal:
                return self.read_decimal(fp)
            raise TypeError()
        byte_value = fp.read(size)
        return primitive_class(byte_value)

    def read_record(self, fp: 'BinaryIO') -> bool:
        record_type_byte = fp.read(1)[0]
        record_type = enums.RecordType(record_type_byte)
        if record_type == enums.RecordType.MessageEnd:
            return False

        read_fn = self._read_record_fn[record_type]
        if read_fn is None:
            raise NotImplementedError("Record read function not implemented for {}".format(record_type.name))
        value = read_fn(fp)
        if value is not None:
            value_type = type(value)
            if issubclass(value_type, objects.Instance):
                inst = value  # type: Instance
                if value_type is not objects.InstanceReference:
                    self._state.objects[inst.object_id] = inst
                    self._data_store.objects[inst.object_id] = inst

        return True

    def read_reference(self, fp: 'BinaryIO') -> 'objects.InstanceReference':
        state_object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        reference = objects.InstanceReference(state_object_id, self._data_store)
        self._state.references.append(reference)
        return reference

    def read_string(self, fp: 'BinaryIO') -> 'String':
        length = utils.read_multi_byte_int(fp)
        if length < 0:
            if self._strict:
                raise ValueError("Negative length while reading string")
            length = 0
        return primitives.String(fp.read(length).decode('utf-8'))

    def read_string_array(self, fp: 'BinaryIO') -> 'Instance':
        # TODO: Change this to string specific code
        return self.read_object_array(fp)

    def read_system_class_full(self, fp: 'BinaryIO') -> 'ClassInstance':
        class_info = structs.ClassInfo.read(fp)
        member_type_info = structs.MemberTypeInfo.read(fp, len(class_info.members))
        library = self._data_store.libraries[-1]
        class_obj = self.build_class(class_info, library, member_type_info)
        return self.read_class_instance(fp, class_info.object_id.value, class_obj)

    def read_system_class_partial(self, fp: 'BinaryIO') -> 'ClassInstance':
        class_info = structs.ClassInfo.read(fp)
        library = self._data_store.libraries[-1]
        class_obj = self.build_class(class_info, library, None)
        return self.read_class_instance(fp, class_info.object_id.value, class_obj)

    def write(self, fp: 'BinaryIO', value: 'Instance') -> None:
        object_id = 1
        library_id = 1
