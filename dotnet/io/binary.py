
import struct

import dotnet.enum as enums
import dotnet.io.base as base
import dotnet.primitives as primitives
import dotnet.object as objects
import dotnet.structures as structs
import dotnet.utils as utils

import typing
if typing.TYPE_CHECKING:
    from typing import Any, BinaryIO, Dict, List, Optional, Set, Tuple, Type, Union

    from dotnet.enum import PrimitiveType
    from dotnet.object import ClassObject, ClassInstance, DataStore, Instance, InstanceReference, Library,\
        PrimitiveArray, ObjectArray, StringArray, StringInstance
    from dotnet.primitives import Boolean, Byte, Char, DateTime, Decimal, Double, Int8, Int16, Int32, Int64, \
        Primitive, String, Single, TimeSpan, UInt16, UInt32, UInt64
    from dotnet.structures import ClassInfo, MemberTypeInfo


class BinaryReader(base.Reader):
    @classmethod
    def binary(cls) -> bool:
        return True

    def __init__(self, data_store: 'Optional[DataStore]'=None, **kwargs) -> None:
        self._data_store = data_store if data_store is not None else objects.DataStore.get_global()
        self._root_id = 0
        self._objects = dict()  # type: Dict[int, Instance]
        self._libraries = dict()  # type: Dict[int, Library]
        self._library_id_map = dict()  # type: Dict[int, int]
        self._reference_parents = list()  # type: List[Instance]
        self._strict = not bool(kwargs.pop('permissive', False))
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
            None,  # TODO: Add an error function for gaps
            None,
            None
        ]

    def reset(self) -> None:
        self._root_id = 0
        self._objects.clear()
        self._libraries.clear()
        self._library_id_map.clear()
        self._reference_parents.clear()

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
        self.reset()
        self.read_header(fp, True)
        while self.read_record(fp):
            pass

        self.resolve_references()
        root_value = self._objects[self._root_id]
        self.reset()
        return root_value

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
                    ci.class_object.value_type = True
                    data.append(ci)
                else:
                    data.append(value)

        array = objects.BinaryArray(rank, array_type, lengths, offsets, bin_type, additional_info, data,
                                    self._data_store)
        self.register_object(array, state_object_id)
        if references:
            self._reference_parents.append(array)
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
        class_inst = objects.ClassInstance(class_obj, data, self._data_store)
        self.register_object(class_inst, state_obj_id)
        if references:
            self._reference_parents.append(class_inst)
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
        metadata_obj = self._objects[metadata_id]
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
        library = self._libraries[state_library_id]
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
        library = self._libraries[library_id]
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

        self._root_id = root_id
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
        self._library_id_map[state_lib_id] = library.id
        self._libraries[state_lib_id] = library
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
        while len(data) < length:
            record_byte = fp.read(1)[0]
            record_type = enums.RecordType(record_byte)
            read_fn = self._read_record_fn[record_type]
            value = read_fn(fp)
            value_type = type(value)
            if value_type is structs.NullReferenceMultiple:
                value: structs.NullReferenceMultiple
                data.extend(value)
            else:
                if value_type is InstanceReference:
                    value: 'InstanceReference'
                    has_references = True
                elif value_type is ClassInstance:
                    value: 'ClassInstance'
                    value.class_object.value_type = True

                data.append(value)

        array = objects.ObjectArray(data, self._data_store)
        self.register_object(array, state_object_id)
        if has_references:
            self._reference_parents.append(array)
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

        array = objects.PrimitiveArray(type_class, values, self._data_store)
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
                return primitives.String(self.read_string_raw(fp))
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
                return primitives.String(self.read_string_raw(fp))
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
        reference = objects.InstanceReference(state_object_id, self._objects)
        return reference

    def read_string(self, fp: 'BinaryIO') -> 'objects.StringInstance':
        """Read a String primitive from the stream

        This method implements the BinaryObjectString record of the NRBF
        protocol.

        :param fp: The stream to read the string from
        :return: A String primitive
        """
        state_object_id = int.from_bytes(fp.read(4), 'little', signed=True)
        str_value = self.read_string_raw(fp)
        value = objects.StringInstance(str_value, self._data_store)
        self._objects[state_object_id] = value
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

        data = list()  # type: List[Optional[str]]
        while len(data) < length:
            record_type_byte = fp.read(1)[0]
            record_type = enums.RecordType(record_type_byte)
            if record_type == enums.RecordType.BinaryObjectString:
                data.append(self.read_string(fp).value)
            elif record_type == enums.RecordType.ObjectNull:
                data.append(None)
            elif record_type == enums.RecordType.ObjectNullMultiple:
                data.extend(self.read_null_multiple(fp))
            elif record_type == enums.RecordType.ObjectNullMultiple256:
                data.extend(self.read_null_multiple_256(fp))
            elif record_type == enums.RecordType.MemberReference:
                ref = self.read_reference(fp)
                # The string array only uses a reference if the string has
                # previously been written/read
                # This means we can and should look it up immediately
                str_inst = ref.resolve()
                value_type = type(str_inst)
                if (value_type is not str and value_type is not primitives.String
                        and value_type is not objects.StringInstance):
                    raise TypeError("String Array contains reference to invalid type")
                data.append(str(str_inst))
            else:
                raise ValueError("Expected string or Null, got {}".format(record_type.name))

        array = objects.StringArray(data, self._data_store)
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
        bytes_string = fp.read(length)
        if len(bytes_string) != length:
            raise IOError("Unexpected EOF while reading string value")
        str_value = bytes_string.decode('utf-8')
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
        if state_object_id in self._objects.keys():
            raise ValueError("Object with ID {} already read from stream".format(state_object_id))
        self._objects[state_object_id] = inst

    def resolve_references(self) -> None:
        """Resolve all unresolved references

        This method remaps all InstanceReferences to the correct object
        id. This method fails if there are dangling references, so it
        should only be used after the stream has been fully read.

        This method is called automatically by the
        BinaryFormatter.read() method.
        """
        for ref_parent in self._reference_parents:
            ref_parent.resolve_references(self._objects)

        self._reference_parents.clear()


class BinaryWriter(base.Writer):
    @classmethod
    def binary(cls) -> bool:
        return True

    def __init__(self, data_store: 'Optional[DataStore]'=None, **kwargs) -> None:
        self._data_store = data_store if data_store is not None else objects.DataStore.get_global()
        self._strict = not bool(kwargs.pop("permissive", False))
        self._object_map = dict()  # type: Dict[int, int]
        self._string_pool = dict()  # type: Dict[str, int]
        self._class_set = set()  # type: Set[ClassObject]
        self._library_map = dict()  # type: Dict[Library, int]
        self._object_cache = list()  # type: List[Instance]
        self._next_obj_id = 1
        self._next_inline_obj_id = -1

        self._write_primitive_lookup = [
            None,  # TODO: Add an error function for gaps
            self.write_bool,
            self.write_byte,
            self.write_char,
            None,
            self.write_decimal,
            self.write_double,
            self.write_int16,
            self.write_int32,
            self.write_int64,
            self.write_int8,
            self.write_single,
            self.write_time_span,
            self.write_date_time,
            self.write_uint16,
            self.write_uint32,
            self.write_uint64,
            self.write_null,
            self.write_string
        ]

    def get_object_id(self, item: 'Any', do_not_cache: bool=False, inline_definition: bool=False) -> int:
        item_id = id(item)
        object_id = self._object_map.get(item_id, 0)
        if object_id != 0:
            return object_id

        if inline_definition:
            object_id = self._next_inline_obj_id
            self._next_inline_obj_id += 1
            # TODO: Check for 32-bit signed overflow
        else:
            self._object_cache.append(item)
            object_id = self._next_obj_id
            self._next_obj_id += 1

        if not do_not_cache:
            self._object_map[item_id] = object_id

        return object_id

    def write(self, fp: 'BinaryIO', value: 'Instance') -> None:
        self.write_header(fp, 1, 1, 1, 0)
        self.write_instance(fp, value)
        while len(self._object_cache) > 0:
            obj = self._object_cache.pop(0)
            self.write_instance(fp, obj)
        fp.write(b'\x0B')

    def write_binary_string_record(self, fp: 'BinaryIO', value: 'Union[str, String, StringInstance]'):
        # String pooling; check if we have already written the given string
        str_val = str(value)
        object_id = self._string_pool.get(str_val, 0)
        if object_id == 0:
            object_id = self.get_object_id(StringInstance(str_val))
            fp.write(b'\x06')
            fp.write(object_id.to_bytes(4, 'little', signed=True))
            self.write_string(fp, str(value))
        else:
            fp.write(b'\x09')
            fp.write(object_id.to_bytes(4, 'little', signed=True))

    @staticmethod
    def write_bool(fp: 'BinaryIO', value: 'Union[bool, Boolean]') -> None:
        fp.write(b'\x01' if bool(value) else b'\x00')

    @staticmethod
    def write_byte(fp: 'BinaryIO', value: 'Union[int, Byte]') -> None:
        fp.write(int(value).to_bytes(1, 'little', signed=False))

    @staticmethod
    def write_char(fp: 'BinaryIO', value: 'Union[str, Char]') -> None:
        fp.write(str(value)[0].encode('utf-8'))

    def write_class_instance(self, fp: 'BinaryIO', value: 'ClassInstance') -> None:
        # TODO: Implement the write_class_instance() method
        pass

    def write_class(self, fp: 'BinaryIO', value: 'ClassObject') -> None:
        # TODO: Implement the write_class() method
        pass

    @staticmethod
    def write_date_time(fp: 'BinaryIO', value: 'DateTime') -> None:
        fp.write(int(value).to_bytes(8, 'little', signed=True))

    @staticmethod
    def write_decimal(fp: 'BinaryIO', value: 'Union[float, int, Decimal]') -> None:
        decimal = utils.move(value, primitives.Decimal)
        fp.write(str(decimal).encode('utf-8'))

    @staticmethod
    def write_double(fp: 'BinaryIO', value: 'Union[float, Double]') -> None:
        fp.write(struct.pack('<d', float(value)))

    @staticmethod
    def write_header(fp: 'BinaryIO', root_id: int, header_id: int, major_version: int=1, minor_version: int=1) -> None:
        fp.write(b'\x00')
        fp.write(root_id.to_bytes(4, 'little', signed=True))
        fp.write(header_id.to_bytes(4, 'little', signed=True))
        fp.write(major_version.to_bytes(4, 'little', signed=True))
        fp.write(minor_version.to_bytes(4, 'little', signed=True))

    def write_instance(self, fp: 'BinaryIO', value: 'Instance') -> None:
        value_type = type(value)
        if issubclass(value_type, objects.ClassInstance):
            value: objects.ClassInstance
            self.write_class_instance(fp, value)
        elif issubclass(value_type, objects.ObjectArray):
            value: objects.ObjectArray
            self.write_object_array(fp, value)
        elif issubclass(value_type, objects.StringArray):
            value: objects.StringArray
            self.write_string_array(fp, value)
        elif issubclass(value_type, objects.PrimitiveArray):
            value: objects.PrimitiveArray
            self.write_primitive_array(fp, value)
        else:
            raise TypeError("Unknown Instance type: {}".format(value_type.__name__))

    @staticmethod
    def write_int8(fp: 'BinaryIO', value: 'Union[int, Int8]') -> None:
        fp.write(int(value).to_bytes(1, 'little', signed=True))

    @staticmethod
    def write_int16(fp: 'BinaryIO', value: 'Union[int, Int16]') -> None:
        fp.write(int(value).to_bytes(2, 'little', signed=True))

    @staticmethod
    def write_int32(fp: 'BinaryIO', value: 'Union[int, Int32]') -> None:
        fp.write(int(value).to_bytes(4, 'little', signed=True))

    @staticmethod
    def write_int64(fp: 'BinaryIO', value: 'Union[int, Int64]') -> None:
        fp.write(int(value).to_bytes(8, 'little', signed=True))

    @staticmethod
    def write_library(fp: 'BinaryIO', value: 'Library') -> None:
        pass

    @staticmethod
    def write_null(fp: 'BinaryIO') -> None:
        pass

    @staticmethod
    def write_null_record(fp: 'BinaryIO', count: int=1) -> None:
        if count <= 0:
            raise ValueError("Null count must be greater than 0")

        if count == 1:
            fp.write(b'\x0A')
        elif count < 256:
            fp.write(b'\x0D')
            fp.write(count.to_bytes(1, 'little', signed=False))
        else:
            fp.write(b'\x0E')
            fp.write(count.to_bytes(4, 'little', signed=False))

    def write_primitive(self, fp: 'BinaryIO', value: 'Primitive') -> None:
        write_fn = self._write_primitive_lookup[value.type]
        if write_fn is None:
            raise ValueError("Write function for {} not implemented".format(value.type.name))
        write_fn(fp, value)

    def write_object_array(self, fp: 'BinaryIO', value: 'ObjectArray') -> None:
        is_value_type = value.is_value_type_array()

        # Write any libraries that we need before the binary array record
        # This is only necessary for value type arrays, as non-value type
        # arrays do not define their members inline
        if is_value_type:
            for lib in value.get_libraries():
                self.write_library(fp, lib)

        fp.write(b'\x10')
        object_id = self.get_object_id(value)
        fp.write(object_id.to_bytes(4, 'little', signed=True))
        fp.write(len(value).to_bytes(4, 'little', signed=True))

        # If we don't have any values, exit now
        if len(value) == 0:
            return

        if is_value_type:
            for item in value.data:
                self.write_class_instance(fp, item)
        else:
            null_count = 0
            for item in value.data:
                if item is None:
                    null_count += 1
                else:
                    # Flush any nulls
                    if null_count > 0:
                        self.write_null_record(fp, null_count)
                        null_count = 0

                    self.write_reference(fp, item)

    def write_primitive_array(self, fp: 'BinaryIO', value: 'PrimitiveArray') -> None:
        fp.write(b'\x0F')
        object_id = self.get_object_id(value)
        fp.write(object_id.to_bytes(4, 'little', signed=True))
        fp.write(len(value).to_bytes(4, 'little', signed=True))
        # TODO: Find a way to get the enum without creating a new instance of the primitive
        primitive_type = value.primitive_class().type  # type: PrimitiveType
        fp.write(primitive_type.to_bytes(1, 'little', signed=False))

        write_fn = self._write_primitive_lookup[primitive_type]
        if write_fn is None:
            raise ValueError("Write function for {} not implemented".format(primitive_type.name))
        for value in value.data:
            write_fn(fp, value)

    def write_reference(self, fp: 'BinaryIO', item: 'Union[Instance, str]') -> None:
        object_id = self.get_object_id(item)
        fp.write(b'\x09')
        fp.write(object_id.to_bytes(4, 'little', signed=True))

    @staticmethod
    def write_single(fp: 'BinaryIO', value: 'Union[float, Single]') -> None:
        fp.write(struct.pack('<f', float(value)))

    @staticmethod
    def write_string(fp: 'BinaryIO', value: 'Union[str, String]') -> None:
        byte_str = str(value).encode('utf-8')
        fp.write(utils.encode_multi_byte_int(len(byte_str)))
        fp.write(byte_str)

    def write_string_array(self, fp: 'BinaryIO', value: 'StringArray') -> None:
        # TODO: Implement the write_string_array() method
        pass

    @staticmethod
    def write_time_span(fp: 'BinaryIO', value: 'TimeSpan') -> None:
        fp.write(value.value.to_bytes(8, 'little', signed=False))

    @staticmethod
    def write_uint16(fp: 'BinaryIO', value: 'Union[int, UInt16]') -> None:
        fp.write(int(value).to_bytes(2, 'little', signed=False))

    @staticmethod
    def write_uint32(fp: 'BinaryIO', value: 'Union[int, UInt32]') -> None:
        fp.write(int(value).to_bytes(4, 'little', signed=False))

    @staticmethod
    def write_uint64(fp: 'BinaryIO', value: 'Union[int, UInt64]') -> None:
        fp.write(int(value).to_bytes(8, 'little', signed=False))
