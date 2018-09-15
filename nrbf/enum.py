
import enum


@enum.unique
class RecordType(enum.IntEnum):
    SerializedStreamHeader = 0
    ClassWithId = 1
    SystemClassWithMembers = 2
    ClassWithMembers = 3
    SystemClassWithMembersAndTypes = 4
    ClassWithMembersAndTypes = 5
    BinaryObjectString = 6
    BinaryArray = 7
    MemberPrimitiveTyped = 8
    MemberReference = 9
    ObjectNull = 10
    MessageEnd = 11
    BinaryLibrary = 12
    ObjectNullMultiple256 = 13
    ObjectNullMultiple = 14
    ArraySinglePrimitive = 15
    ArraySingleObject = 16
    ArraySingleString = 17
    MethodCall = 18
    MethodReturn = 22


@enum.unique
class ClassDefinitionType(enum.IntEnum):
    @staticmethod
    def get(record_type: 'RecordType') -> 'ClassDefinitionType':
        if (record_type == RecordType.ClassWithMembersAndTypes
                or record_type == RecordType.SystemClassWithMembersAndTypes):
            return ClassDefinitionType.Full
        if record_type == RecordType.ClassWithMembers or record_type == RecordType.SystemClassWithMembers:
            return ClassDefinitionType.Partial
        if record_type == RecordType.ClassWithId:
            return ClassDefinitionType.Reference
        return ClassDefinitionType.NotClass

    NotClass = 0
    Reference = 1
    Partial = 2
    Full = 3


@enum.unique
class BinaryType(enum.IntEnum):
    Primitive = 0
    String = 1
    Object = 2
    SystemClass = 3
    Class = 4
    ObjectArray = 5
    StringArray = 6
    PrimitiveArray = 7


@enum.unique
class PrimitiveType(enum.IntEnum):
    Boolean = 1
    Byte = 2
    Char = 3
    Decimal = 5
    Double = 6
    Int16 = 7
    Int32 = 8
    Int64 = 9
    SByte = 10
    Single = 11
    TimeSpan = 12
    DateTime = 13
    UInt16 = 14
    UInt32 = 15
    UInt64 = 16
    Null = 17
    String = 18


@enum.unique
class BinaryArrayType(enum.IntEnum):
    Single = 0
    Jagged = 1
    Rectangular = 2
    SingleOffset = 3
    JaggedOffset = 4
    RectangularOffset = 5


@enum.unique
class MessageFlags(enum.IntEnum):
    NoArgs = 1 << 0
    ArgsInline = 1 << 1
    ArgsIsArray = 1 << 2
    ArgsInArray = 1 << 3
    NoContext = 1 << 4
    ContextInline = 1 << 5
    ContextInArray = 1 << 6
    MethodSignatureInArray = 1 << 7
    PropertiesInArray = 1 << 8
    NoReturnValue = 1 << 9
    ReturnValueVoid = 1 << 10
    ReturnValueInline = 1 << 11
    ReturnValueInArray = 1 << 12
    ExceptionInArray = 1 << 13
    GenericMethod = 1 << 14
