
from abc import ABC, abstractmethod

import dotnet.exceptions as exceptions


import typing
if typing.TYPE_CHECKING:
    from typing import IO
    from dotnet.object import Instance


class Reader(ABC):
    @classmethod
    @abstractmethod
    def binary(cls) -> bool:
        raise exceptions.ClassMethodNotImplemented(cls, "binary()")

    @abstractmethod
    def read(self, fp: 'IO') -> 'Instance':
        raise exceptions.MethodNotImplemented(self, "read()")

    def read_file(self, filename: str) -> 'Instance':
        with open(filename, 'rb' if type(self).binary() else 'r') as fp:
            return self.read(fp)


class Writer(ABC):
    @classmethod
    @abstractmethod
    def binary(cls) -> bool:
        raise exceptions.ClassMethodNotImplemented(cls, "binary()")

    @abstractmethod
    def write(self, fp: 'IO', value: 'Instance') -> None:
        raise exceptions.MethodNotImplemented(self, "write()")

    def write_file(self, filename: str, value: 'Instance') -> None:
        with open(filename, 'wb' if type(self).binary() else 'w') as fp:
            self.write(fp, value)
