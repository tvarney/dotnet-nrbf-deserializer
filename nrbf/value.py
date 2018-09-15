
from abc import ABCMeta, abstractmethod

import typing
if typing.TYPE_CHECKING:
    from typing import BinaryIO


class Value(object, metaclass=ABCMeta):
    @abstractmethod
    def write(self, fp: 'BinaryIO') -> None:
        raise NotImplementedError("{}::write() not implemented")

    @abstractmethod
    def __bytes__(self) -> bytes:
        raise NotImplementedError("{}::__bytes__() not implemented")

    def __str__(self) -> str:
        return repr(self)
