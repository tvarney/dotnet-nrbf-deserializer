
import typing
if typing.TYPE_CHECKING:
    from typing import Any
    from nrbf.enum import RecordType


class MethodNotImplemented(NotImplementedError):
    def __init__(self, instance: 'Any', method_name: str) -> None:
        NotImplementedError.__init__(self, "{}::{} not implemented".format(type(instance).__name__, method_name))


class ClassMethodNotImplemented(NotImplementedError):
    def __init__(self, cls: 'type', method_name: str) -> None:
        NotImplementedError.__init__(self, "{}::{} not implemented".format(cls.__name__, method_name))


class RecordTypeError(IOError):
    def __init__(self, expected: 'RecordType', found: 'RecordType'):
        IOError.__init__(self, "Expected RecordType.{}, read RecordType.{}".format(expected.name, found.name))
