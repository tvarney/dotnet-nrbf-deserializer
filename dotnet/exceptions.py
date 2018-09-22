
import typing
if typing.TYPE_CHECKING:
    from typing import Any
    from dotnet.enum import BinaryType, RecordType
    from dotnet.structures import ExtraInfoType


class MethodNotImplemented(NotImplementedError):
    def __init__(self, instance: 'Any', method_name: str) -> None:
        NotImplementedError.__init__(self, "{}::{} not implemented".format(type(instance).__name__, method_name))


class ClassMethodNotImplemented(NotImplementedError):
    def __init__(self, cls: 'type', method_name: str) -> None:
        NotImplementedError.__init__(self, "{}::{} not implemented".format(cls.__name__, method_name))


class RecordTypeError(IOError):
    def __init__(self, expected: 'RecordType', found: 'RecordType') -> None:
        IOError.__init__(self, "Expected RecordType.{}, read RecordType.{}".format(expected.name, found.name))


class InvalidExtraInfoValue(ValueError):
    def __init__(self, extra_info_value: 'ExtraInfoType', binary_type: 'BinaryType') -> None:
        ValueError.__init__(self, "Invalid extra type info of type {} for BinaryType.{}".format(
            type(extra_info_value).__name__,
            binary_type.name
        ))


class InvalidReferenceError(RuntimeError):
    pass


class NullReferenceError(InvalidReferenceError):
    pass
