
import abc


class Value(abc.ABC):
    def __str__(self) -> str:
        return repr(self)
