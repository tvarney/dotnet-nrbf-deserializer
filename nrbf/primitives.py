
from abc import ABCMeta, abstractmethod

from nrbf.value import Value

import typing
if typing.TYPE_CHECKING:
    from typing import Any, BinaryIO
    from nrbf.enum import PrimitiveType


class Primitive(Value, metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def read(cls, fp: 'BinaryIO') -> 'Primitive':
        raise NotImplementedError("{}::read() not implemented".format(cls.__name__))

    @property
    @abstractmethod
    def value(self) -> 'Any':
        raise NotImplementedError("{}::value::get not implemented".format(type(self).__name__))

    @value.setter
    @abstractmethod
    def value(self, new_value: 'Any') -> None:
        raise NotImplementedError("{}::value::set not implemented".format(type(self).__name__))

    @property
    @abstractmethod
    def type(self) -> 'PrimitiveType':
        raise NotImplementedError("{}::type not implemented".format(type(self).__name__))

    def write(self, fp: 'BinaryIO') -> None:
        fp.write(bytes(self))
