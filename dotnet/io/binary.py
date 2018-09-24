
import dotnet.enum as enums
import dotnet.io.base as base
import dotnet.primitives as primitives
import dotnet.object as objects
import dotnet.structures as structs
import dotnet.utils as utils

import typing
if typing.TYPE_CHECKING:
    from typing import BinaryIO, Dict, List, Optional, Tuple, Type, Union

    from dotnet.enum import PrimitiveType
    from dotnet.object import ClassObject, ClassInstance, DataStore, Instance, InstanceReference, Library,\
        PrimitiveArray, ObjectArray, StringArray
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
            self.reference_parents = list()

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

    def build_class(self, class_info: 'ClassInfo', library: 'Library',
                    member_info: 'Optional[MemberTypeInfo]') -> 'ClassObject':
        """Create a ClassObject and register it to the data store

        If the member information is not given, this method attempts to
        get it from the metadata collection of the data store.

        :param class_info: The ClassInfo struct for the class
        :param library: The library the class is a part of
        :param member_info: Information about the members of the class
        :return: A ClassObject built from the parameters
        """
        if member_info is None:
            partial = True
            members = self._data_store.metadata.get((library.id, class_info.name), None)
        else:
            partial = False
            member_count = len(class_info.members)
            if member_count != len(member_info.binary_types):
                raise ValueError("Mismatch between members names and member type info")

            members = list()  # type: List[objects.Member]
            for i in range(member_count):
                members.append(objects.Member(
                    i, class_info.members[i], member_info.binary_types[i], member_info.extra_info[i]
                ))

        class_obj = objects.ClassObject(class_info.name, members, partial, library, self._data_store)
        old_class_obj = self._data_store.classes.get(class_obj.key, None)
        if old_class_obj is None:
            self._data_store.classes[class_obj.key] = class_obj
            return class_obj
        else:
            if old_class_obj != class_obj:
                raise ValueError("Non-duplicate classes of same name in same library")
            return old_class_obj

    def read(self, fp: 'BinaryIO') -> 'Instance':
        """Read all records from the stream

        This method will read every record that is present in the stream
        up to the first MessageEnd record. This may not be the entirety
        of the file if there are multiple messages in the stream.

        This message then resolves all references, then returns the root
        object from the stream.

        :param fp: The binary stream to read records from
        :return: The root object from the stream
        """
        # TODO: Reset the state each time this is called
        self.read_header(fp, True)
        while self.read_record(fp):
            pass

        self.resolve_references()
        return self._state.objects[self._state.root_id]

    def read_binary_array(self, fp: 'BinaryIO') -> 'objects.BinaryArray':
        """Read a binary array from the stream

        This method implements the BinaryArray record of the NRBF
        protocol.

        :param fp: The stream to read the array from
        :return: A BinaryArray instance
        """
        state_object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        array_type_byte = fp.read(1)[0]
        array_type = enums.BinaryArrayType(array_type_byte)
        rank = int.from_bytes(fp.read(4), 'little', signed=True)
        if rank < 1:
            raise ValueError("Invalid binary array rank {}".format(rank))

        total_length = 1
        lengths = list()  # type: List[int]
        for _ in range(rank):
            length = int.from_bytes(fp.read(4), 'little', signed=True)
            if length < 0:
                raise ValueError("Invalid binary array length {}".format(length))
            total_length *= length
            lengths.append(length)

        offsets = None
        if (array_type == enums.BinaryArrayType.JaggedOffset or array_type == enums.BinaryArrayType.RectangularOffset or
                array_type == enums.BinaryArrayType.SingleOffset):
            offsets = list()  # type: List[int]
            for _ in range(rank):
                offset = int.from_bytes(fp.read(4), 'little', signed=True)
                offsets.append(offset)

        bin_type_byte = fp.read(1)[0]
        bin_type = enums.BinaryType(bin_type_byte)
        additional_info = self.read_extra_type_info(fp, bin_type)
        references = False
        data = list()
        if bin_type == enums.BinaryType.Primitive:
            for _ in range(total_length):
                data.append(self.read_primitive_type(fp, additional_info))
        else:
            while len(data) < total_length:
                record_type_byte = fp.read(1)[0]
                record_type = enums.RecordType(record_type_byte)
                read_fn = self._read_record_fn[record_type]
                if read_fn is None:
                    raise ValueError("Unexpected record {} while reading binary array members".format(record_type.name))
                value = read_fn(fp)
                if type(value) is objects.InstanceReference:
                    references = True
                    data.append(value)
                elif type(value) is structs.NullReferenceMultiple:
                    nrm = value  # type: structs.NullReferenceMultiple
                    data.extend(nrm)
                elif type(value) is objects.ClassInstance:
                    ci = value  # type: ClassInstance
                    # TODO: Mark the underlying ClassObject as a ValueType
                    data.append(ci)
                else:
                    data.append(value)

        object_id = self._data_store.get_object_id()
        array = objects.BinaryArray(object_id, rank, array_type, lengths, offsets, bin_type, additional_info, data)
        self.register_object(array, state_object_id)
        if references:
            self._state.reference_parents.append(array)
        return array

    @staticmethod
    def read_char(fp: 'BinaryIO') -> 'Char':
        """Read a character from the stream

        This method is split out from the standard primitive reading
        function because a character is of variable size. Characters
        in a NRBF stream are utf-8 encoded, which may require between
        1 and 4 bytes to fully decode.

        :param fp: The stream to read a character from
        :return: A Char primitive read from the stream
        """
        bytes_value = fp.read(1)
        first_byte = bytes_value[0]
        if first_byte > 127:
            if first_byte >= 0xF0:
                return primitives.Char(bytes_value + fp.read(3))
            if first_byte >= 0xE0:
                return primitives.Char(bytes_value + fp.read(2))
            return primitives.Char(bytes_value + fp.read(1))
        return primitives.Char(bytes_value)

    def read_class_info(self, fp: 'BinaryIO') -> 'structs.ClassInfo':
        """Read a ClassInfo struct from the stream

        See the documentation of the ClassInfo object in the
        dotnet.structures package for more information.

        :param fp: The stream to read the ClassInfo from
        :return: A ClassInfo structure
        """
        object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        name = self.read_string_raw(fp)
        member_count = int.from_bytes(fp.read(4), 'little', signed=True)
        members = list()
        for _ in range(member_count):
            members.append(self.read_string_raw(fp))
        return structs.ClassInfo(object_id, name, members)

    def read_class_instance(self, fp: 'BinaryIO', state_obj_id: int, class_obj: 'ClassObject') -> 'ClassInstance':
        """Read an instance of the given ClassObject from the stream

        :param fp: The stream to read the instance from
        :param state_obj_id: The stream state object id of the object
        :param class_obj: The ClassObject to create an instance from
        :return: An instance of the given ClassObject
        """
        data = list()
        null_count = 0
        references = False
        for member in class_obj.members:
            if null_count > 0:
                if member.binary_type == enums.BinaryType.Primitive:
                    raise ValueError("Encountered Null reference for primitive value")
                data.append(None)
                null_count -= 1
            elif member.binary_type == enums.BinaryType.Primitive:
                data.append(self.read_primitive_type(fp, member.extra_info))
            else:
                record_byte = fp.read(1)[0]
                record_type = enums.RecordType(record_byte)
                read_fn = self._read_record_fn[record_type]
                value = read_fn(fp)
                value_type = type(value)
                if value_type is structs.NullReferenceMultiple:
                    nrm = value  # type: structs.NullReferenceMultiple
                    null_count = len(nrm)
                else:
                    if value_type is objects.InstanceReference:
                        references = True
                    data.append(value)
        obj_id = self._data_store.get_object_id()
        class_inst = objects.ClassInstance(obj_id, class_obj, data)
        self.register_object(class_inst, state_obj_id)
        if references:
            self._state.reference_parents.append(class_inst)
        return class_inst

    def read_class_type_info(self, fp: 'BinaryIO') -> 'structs.ClassTypeInfo':
        """Read class type information from the stream

        See the ClassTypeInfo documentation in the dotnet.structures
        package fcr more information.

        :param fp: The stream to read the ClassTypeInfo from
        :return: A ClassTypeInfo structure
        """
        class_name = self.read_string_raw(fp)
        library_id = int.from_bytes(fp.read(4), 'little', signed=True)
        return structs.ClassTypeInfo(class_name, library_id)

    def read_class_with_id(self, fp: 'BinaryIO') -> 'ClassInstance':
        """Read a class instance from the stream using metadata

        This method implements the ClassWithID record of the NRBF
        protocol.

        The ClassWithID record uses the class information built by a
        previous object in the stream to read a class instance from the
        stream.

        The ClassWithID record consists of two signed int32, one for the
        object_id of the new class record, and one for the already
        created object to use the ClassObject from.

        :param fp: The stream to read the class instance from
        :return: A class instance
        """
        object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        metadata_id = int.from_bytes(fp.read(4), 'little', signed=True)
        metadata_obj = self._state.objects[metadata_id]
        if type(metadata_obj) is objects.ClassInstance:
            class_inst = metadata_obj  # type: ClassInstance
            class_obj = class_inst.class_object
            return self.read_class_instance(fp, object_id, class_obj)
        raise ValueError("ClassWithId references non-class instance for metadata")

    def read_class_full(self, fp: 'BinaryIO') -> 'ClassInstance':
        """Read a class instance from the stream

        This method implements the ClassWithMembersAndTypes record of
        the NRBF protocol.

        The record consists of a ClassInfo structure, followed by a
        MemberTypeInfo structure, then a stream state library id
        (int32), then the actual instance data.

        :param fp: The stream to read the class instance from
        :return: A class instance
        """
        class_info = self.read_class_info(fp)
        member_type_info = self.read_member_type_info(fp, class_info.members)
        state_library_id = int.from_bytes(fp.read(4), 'little', signed=True)
        library = self._state.libraries[state_library_id]
        class_obj = self.build_class(class_info, library, member_type_info)
        return self.read_class_instance(fp, class_info.object_id, class_obj)

    def read_class_partial(self, fp: 'BinaryIO') -> 'ClassInstance':
        """Read a class instance from the stream

        This method implements the ClassWithMembers record of the NRBF
        protocol.

        The record consists of a ClassInfo structure, followed by a
        stream state library id (int32), then the actual instance data.

        As the record does not contain any information about the members
        of the class beyond the names, this method will fail if the
        member metadata is not specified in a MemberTypeInfo in the
        DataStore's metadata lookup dictionary.

        :param fp: The stream to read the class instance from
        :return: A class instance
        """
        class_info = self.read_class_info(fp)
        library_id = int.from_bytes(fp.read(4), 'little', signed=True)
        library = self._state.libraries[library_id]
        class_obj = self.build_class(class_info, library, None)
        return self.read_class_instance(fp, class_info.object_id, class_obj)

    def read_decimal(self, fp: 'BinaryIO') -> 'Decimal':
        """Read a decimal primitive from the stream

        :param fp: The stream to read the decimal from
        :return: A decimal primitive
        """
        length = utils.read_multi_byte_int(fp)
        if length < 0:
            if self._strict:
                raise ValueError("Negative length while reading decimal")
            length = 0
        return primitives.Decimal(fp.read(length).decode('utf-8'))

    def read_extra_type_info(self, fp: 'BinaryIO', bin_type: 'enums.BinaryType') -> 'structs.ExtraInfoType':
        """Read extra type information about the given binary type

        Multiple structures and records read what is termed
        'additional type information' by the NRBF technical docs. This
        information is used to determine exactly what the stream needs
        to read for the object. As such, this method examines the given
        BinaryType enum, then reads the additional type information from
        the stream (if necessary) and returns it.

        There are essentially 3 cases to consider:
          1. Primitive or PrimitiveArray
          2. SystemClass
          3. Class

        In case 1, a single byte needs to be read from the stream and
        converted into a PrimitiveType enum. This defines the primitive
        type to be read from the stream.

        In case 2, a string is read which denotes the system class which
        must be the type of the argument.

        In case 3, a ClassTypeInfo structure is read, which consists of
        the class name and the state library id (int32) of the library
        the class is defined by.

        :param fp: The stream to read from
        :param bin_type: The binary type to get extra info about
        :return: The extra type information needed for bin_type
        """
        if bin_type == enums.BinaryType.Primitive or bin_type == enums.BinaryType.PrimitiveArray:
            byte_value = fp.read(1)[0]
            return enums.PrimitiveType(byte_value)
        elif bin_type == enums.BinaryType.SystemClass:
            return self.read_string_raw(fp)
        elif bin_type == enums.BinaryType.Class:
            return self.read_class_type_info(fp)
        return None

    def read_header(self, fp: 'BinaryIO', read_record_type: bool=True) -> 'Tuple[int, int, int, int]':
        """Read the stream header from the given stream

        This method implements the SerializationHeader record of the
        NRBF protocol.

        The SerializationHeader record is defined as a series of
        4 int32 values, corresponding to:
          1. root_id: The stream object id of the root object
          2. header_id: 0 or -1
          3. major_version: The major version number of the header
          4. minor_version: The minor version number of the header

        The major version of the stream header must be 1, and the minor
        version of the stream header must be 0 for the stream to be
        considered well formed.

        :param fp: The stream to read the header from
        :param read_record_type: If the record type should be read
        :return: The data from the stream header
        """
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
        """Read a library record from the stream

        This method implements the BinaryLibrary record of the NRBF
        protocol.

        The BinaryLibrary record defines a library as a name and a
        stream library id. The name of the binary library may contain
        extra information about the library, such as the version,
        culture, and public key token of the library.

        :param fp: The stream to read the library from
        :return: A Library instance
        """
        state_lib_id = int.from_bytes(fp.read(4), 'little', signed=True)
        str_value = self.read_string_raw(fp)
        # TODO: check if we have a library which matches this one already
        library = objects.Library.parse_string(str_value)
        library.id = self._data_store.get_library_id()
        self._state.library_id_map[state_lib_id] = library.id
        self._state.libraries[state_lib_id] = library
        return library

    def read_member_type_info(self, fp: 'BinaryIO', member_list: 'List[str]') -> 'structs.MemberTypeInfo':
        """Read a MemberTypeInfo structure from the stream

        See the MemberTypeInfo documentation in the dotnet.structures
        package for more information.

        :param fp: The stream to read the MemberTypeInfo struct from
        :param member_list: A list of members to match
        :return: A MemberTypeInfo structure
        """
        bin_types = list()
        extra_info = list()
        member_count = len(member_list)
        for _ in range(member_count):
            byte_value = fp.read(1)[0]
            bin_type = enums.BinaryType(byte_value)
            bin_types.append(bin_type)

        for bin_type in bin_types:
            extra_info.append(self.read_extra_type_info(fp, bin_type))

        return structs.MemberTypeInfo(bin_types, extra_info)

    @staticmethod
    def read_null(_: 'BinaryIO') -> None:
        """Read a null object reference from the stream

        This method implements the ObjectNull record of the NRBF
        protocol.

        :param _: The stream to read from
        :return: A literal None object
        """
        return None

    @staticmethod
    def read_null_multiple(fp: 'BinaryIO') -> 'structs.NullReferenceMultiple':
        """Read a ObjectNullMultiple record from the stream

        This method implements the ObjectNullMultiple record of the NRBF
        protocol.

        An ObjectNullMultiple record consists of a single int32 value
        denoting how many null references it represents.

        :param fp: The stream to read from
        :return: A list of Null references
        """
        # TODO: Make this method return a generator
        count = int.from_bytes(fp.read(4), 'little', signed=True)
        return structs.NullReferenceMultiple(count)

    @staticmethod
    def read_null_multiple_256(fp: 'BinaryIO') -> 'structs.NullReferenceMultiple':
        """Read a ObjectNullMultiple256 record from the stream

        This method implements the ObjectNullMultiple256 record of the
        NRBF protocol.

        An ObjectNullMultiple record consists of a single byte value
        denoting how many null references it represents.

        :param fp:
        :return:
        """
        # TODO: Make this method return a generator
        count = fp.read(1)[0]
        return structs.NullReferenceMultiple(count)

    def read_object_array(self, fp: 'BinaryIO') -> 'ObjectArray':
        """Read an object array from the stream

        This method implements the ArraySingleObject record of the NRBF
        protocol.

        :param fp: The stream to read the object array from
        :return: An object array instance
        """
        state_object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        length = int.from_bytes(fp.read(4), 'little', signed=True)
        if length < 0:
            if self._strict:
                raise ValueError("Invalid array length while reading array")
            length = 0

        data = list()
        has_references = False
        count = 0
        while count < length:
            record_byte = fp.read(1)[0]
            record_type = enums.RecordType(record_byte)
            read_fn = self._read_record_fn[record_type]
            value = read_fn(fp)
            if type(value) is structs.NullReferenceMultiple:
                value: structs.NullReferenceMultiple
                data.extend(value)
                count += len(value)
            else:
                value: 'Union[Instance, InstanceReference]'
                data.append(value)
                has_references = True
                count += 1

        object_id = self._data_store.get_object_id()
        array = objects.ObjectArray(object_id, data)
        self.register_object(array, state_object_id)
        if has_references:
            self._state.reference_parents.append(self)
        return array

    def read_primitive(self, fp: 'BinaryIO') -> 'Primitive':
        """Read a typed primitive from the stream

        This method implements the MemberPrimitiveTyped record of the
        NRBF protocol.

        This method reads a single byte from the stream to get the
        PrimitiveType of the primitive to read, then delegates to the
        read_primitive_type() method.

        :param fp: The stream to read the primitive from
        :return: A Primitive instance
        """
        primitive_type_byte = fp.read(1)[0]
        primitive_type = enums.PrimitiveType(primitive_type_byte)
        return self.read_primitive_type(fp, primitive_type)

    def read_primitive_array(self, fp: 'BinaryIO') -> 'PrimitiveArray':
        """Read a primitive array from the stream

        This method implements the ArraySinglePrimitive record of the
        NRBF protocol.

        This method reads array information from the stream, which
        consists of the stream state object id of the array, the length
        of the array, and a PrimitiveType enum for the type of the
        array. It then reads the given number of primitives from the
        stream as the array data.

        The primitives that are read from the stream are not marked by
        a RecordType enum, or a PrimitiveType enum beyond that of the
        array itself.

        :param fp: The stream to read the primitive array from
        :return: A PrimitiveArray instance
        """
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
        if value_size <= 0:
            if type_enum == enums.PrimitiveType.Char:
                for _ in range(length):
                    values.append(self.read_char(fp))
            else:
                for _ in range(length):
                    str_len = utils.read_multi_byte_int(fp)
                    values.append(type_class(fp.read(str_len)))
        else:
            for _ in range(length):
                values.append(type_class(fp.read(value_size)))

        object_id = self._data_store.get_object_id()
        array = objects.PrimitiveArray(object_id, type_class, values)
        self.register_object(array, state_object_id)
        return array

    def read_primitive_class(self, fp: 'BinaryIO', primitive_class: 'Type[Primitive]') -> 'Primitive':
        """Read a primitive from the stream using a Primitive class

        This method reads a primitive from the stream using the given
        primitive class to query for the stream size of the primitive.

        This method delegates to read_char(), read_string() and
        read_decimal() for those primitives, as they are of variable
        length.

        :param fp: The stream to read a primitive from
        :param primitive_class: The class of the primitive to read
        :return: A primitive of the same class as given
        """
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
        """Read a primitive from the stream using the PrimitiveType

        This method reads a primitive from the stream using the given
        PrimitiveType enum. This method first looks up the primitive
        class, then uses that to get the size of the primitive in the
        stream.

        This method delegates to the read_char(), read_string() and
        read_decimal() methods for those types, as they are of variable
        length in the stream.

        :param fp: The stream to read the primitive from
        :param primitive_type: The PrimitiveType to read
        :return: A Primitive of the given PrimitiveType
        """
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
        """Read a single record from the stream

        This method reads a single record from the stream, returning
        True if the record was not MessageEnd, or False if it was
        MessageEnd.

        :param fp: The stream to read the record from
        :return: If the record read was not MessageEnd
        """
        record_type_byte = fp.read(1)[0]
        record_type = enums.RecordType(record_type_byte)
        if record_type == enums.RecordType.MessageEnd:
            return False

        read_fn = self._read_record_fn[record_type]
        if read_fn is None:
            raise NotImplementedError("Record read function not implemented for {}".format(record_type.name))
        read_fn(fp)
        return True

    def read_reference(self, fp: 'BinaryIO') -> 'objects.InstanceReference':
        """Read an InstanceReference from the stream

        This method implements the MemberReference record of the NRBF
        protocol.

        The InstanceReference returned by this method will have an
        invalid reference value, as it is populated by the stream state
        object id rather than the data store object id. In order to
        rectify this, call the BinaryFormatter.resolve_references()
        method before attempting to resolve any references.

        Note that the Reference is not guaranteed to be valid until the
        end of the stream; that is, forward references are allowed and
        actually quite common in the standard implementation.

        :param fp: The stream to read the reference from
        :return: An InstanceReference
        """
        state_object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        reference = objects.InstanceReference(state_object_id, self._state.objects)
        self._state.references.append(reference)
        return reference

    def read_string(self, fp: 'BinaryIO') -> 'String':
        """Read a String primitive from the stream

        This method implements the BinaryObjectString record of the NRBF
        protocol.

        :param fp: The stream to read the string from
        :return: A String primitive
        """
        object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        value = primitives.String(self.read_string_raw(fp))
        # TODO: Make a StringInstance?
        self._state.objects[object_id] = value
        return value

    def read_string_array(self, fp: 'BinaryIO') -> 'StringArray':
        """Read an array of strings from the stream

        This method implements the ArraySingleString record of the NRBF
        protocol.

        This method reads array information from the stream first,
        consisting of the stream state object id (int32), and the length
        of the array (int32). It then reads the data from the stream as
        a series of BinaryObjectString records, discarding the record
        type.

        :param fp: The stream to read the string array from
        :return: A StringArray instance
        """
        state_object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        length = int.from_bytes(fp.read(4), 'little', signed=True)

        data = list()  # type: List[str]
        for _ in range(length):
            record_type_byte = fp.read(1)[0]
            record_type = enums.RecordType(record_type_byte)
            if record_type != enums.RecordType.BinaryObjectString:
                raise ValueError("Expected string, got {}".format(record_type.name))
            data.append(self.read_string_raw(fp))

        object_id = self._data_store.get_object_id()
        array = objects.StringArray(object_id, data)
        self.register_object(array, state_object_id)
        return array

    def read_string_raw(self, fp: 'BinaryIO') -> str:
        """Read a string from the stream

        This method reads a raw string from the stream. This does not
        wrap the return value in a String primitive, returning instead
        the native python string representation.

        A string in the NRBF protocol is defined by a multi-byte 31-bit
        int, followed by that many bytes of encoded utf-8 data.

        :param fp: The stream to read the string from
        :return: A string read from the stream
        """
        length = utils.read_multi_byte_int(fp)
        if length < 0:
            if self._strict:
                raise ValueError("Negative length while reading string")
            length = 0
        str_value = fp.read(length).decode('utf-8')
        return str_value

    def read_system_class_full(self, fp: 'BinaryIO') -> 'ClassInstance':
        """Read a system class instance from the stream

        This method implements the SystemClassWithMembersAndTypes record
        of the NRBF protocol.

        This method reads a ClassInfo struct, then a MemberInfo struct
        from the stream, creates a ClassObject from them, then reads
        the class instance data from the stream.

        :param fp: The stream to read the class instance from
        :return: A class instance
        """
        class_info = self.read_class_info(fp)
        member_type_info = self.read_member_type_info(fp, class_info.members)
        library = self._data_store.libraries[-1]
        class_obj = self.build_class(class_info, library, member_type_info)
        return self.read_class_instance(fp, class_info.object_id, class_obj)

    def read_system_class_partial(self, fp: 'BinaryIO') -> 'ClassInstance':
        """Read a partial system class instance from the stream

        This method implements the SystemClassWithMembers record of the
        NRBF protocol.

        This method reads a ClassInfo struct from the stream, then
        attempts to get the member metadata from the attached DataStore.
        The member type information must have been provided by some
        other means before this class is created. It then reads the
        member data from the stream.

        :param fp: The stream to read the class instance from
        :return: A class instance
        """
        class_info = self.read_class_info(fp)
        library = self._data_store.libraries[-1]
        class_obj = self.build_class(class_info, library, None)
        return self.read_class_instance(fp, class_info.object_id, class_obj)

    def register_object(self, inst: 'Instance', state_object_id: int) -> None:
        """Register a newly read object

        This method is intended for internal use only. This method takes
        the given Instance object and maps it into the DataStore and the
        ReadState of the formatter, mapping the two id's together in the
        object_id_map of the ReadState.

        :param inst: The object to register
        :param state_object_id: The stream state object id of the object
        """
        # TODO: Validate that the state_object_id and the instance's object_id aren't already in use
        self._state.objects[state_object_id] = inst
        self._state.object_id_map[state_object_id] = inst.object_id

    def resolve_references(self) -> None:
        """Resolve all unresolved references

        This method remaps all InstanceReferences to the correct object
        id. This method fails if there are dangling references, so it
        should only be used after the stream has been fully read.

        This method is called automatically by the
        BinaryFormatter.read() method.
        """
        for ref_parent in self._state.reference_parents:
            ref_parent.resolve_references(self._state.objects)

        self._state.references.clear()

    def write(self, fp: 'BinaryIO', value: 'Instance') -> None:
        pass
