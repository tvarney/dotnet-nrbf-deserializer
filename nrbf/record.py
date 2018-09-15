
from abc import ABCMeta, abstractmethod

from nrbf.value import Value

import typing
if typing.TYPE_CHECKING:
    from typing import BinaryIO
    from nrbf.enum import RecordType


class Record(Value, metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def read(cls, fp: 'BinaryIO', read_type: bool=False):
        raise NotImplementedError("{}::read() not implemented".format(cls.__name__))

    @property
    @abstractmethod
    def record_type(self) -> 'RecordType':
        raise NotImplementedError("{}::record_type::get not implemented".format(type(self).__name__))
