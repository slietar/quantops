from typing import Generic, TypeVar


K = TypeVar('K')
V = TypeVar('V')

class FrozenDict(dict[K, V], Generic[K, V]):
  def __hash__(self): # type: ignore
    return hash(frozenset(self.items()))

  def __repr__(self):
    return f"{self.__class__.__name__}({super().__repr__()})"
