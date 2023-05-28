import functools
from pprint import pprint
import tomllib
from dataclasses import dataclass, field
from typing import IO, Any, Literal, NewType, NotRequired, Optional, Protocol, Required, Self, TypedDict, cast, final, overload, reveal_type


SUPERSCRIPT_CHARS = {
  "0": "\u2070",
  "1": "\u00b9",
  "2": "\u00b2",
  "3": "\u00b3",
  "4": "\u2074",
  "5": "\u2075",
  "6": "\u2076",
  "7": "\u2077",
  "8": "\u2078",
  "9": "\u2079",
  "-": "\u207b"
}

DimensionName = NewType('DimensionName', str)
PrefixSystemName = NewType('PrefixSystemName', str)
SystemName = NewType('SystemName', str)

Dimensionality = dict[DimensionName, float | int]


class RegistryPrefixData(TypedDict):
  factor: float
  label: str
  symbol: str

class RegistryPrefixSystemData(TypedDict):
  extend: NotRequired[list[PrefixSystemName]]
  prefixes: NotRequired[list[RegistryPrefixData]]

class RegistryUnitData(TypedDict):
  dimensionality: Dimensionality
  label: str | list[str]
  label_names: NotRequired[list[str]]
  symbol: str | list[str]
  symbol_names: NotRequired[list[str]]
  systems: list[SystemName]

  prefixes: NotRequired[list[PrefixSystemName]]

  offset: NotRequired[float]
  value: NotRequired[float]

class RegistryData(TypedDict):
  prefix_systems: dict[PrefixSystemName, RegistryPrefixSystemData]
  units: list[RegistryUnitData]



def compose_dimensionalities(a: Dimensionality, b: Dimensionality, /, factor: int = 1):
  return {
    dimension: power for dimension
      in {*a.keys(), *b.keys()}
      if (power := a.get(dimension, 0) + b.get(dimension, 0) * factor) != 0
  }

def format_superscript(number: float | int, /):
  return str().join(SUPERSCRIPT_CHARS[digit] for digit in str(number))


@final
@functools.total_ordering
@dataclass(frozen=True)
class Quantity:
  dimensionality: Dimensionality
  registry: 'UnitRegistry' = field(repr=False)
  value: float

  def _check_other_dimensionality(self, other: Self, /):
    if self.dimensionality != other.dimensionality:
      raise ValueError("Operation with different dimensionalities")

  def _check_other_registry(self, other: 'CompositeUnit | Self', /):
    if self.registry is not other.registry:
      raise ValueError("Operation with different registries")

  def __hash__(self):
    return hash((frozenset(sorted(self.dimensionality.items())), self.registry, self.value))

  def __eq__(self, other: Self, /):
    self._check_other_dimensionality(other)
    self._check_other_registry(other)

    return self.value == other.value

  def __lt__(self, other: Self, /):
    self._check_other_dimensionality(other)
    self._check_other_registry(other)

    return self.value < other.value

  def __add__(self, other: Self | float | int, /):
    if isinstance(other, (float, int)):
      return self + self.registry.dimensionless(other)

    self._check_other_dimensionality(other)
    self._check_other_registry(other)

    return Quantity(
      dimensionality=self.dimensionality,
      registry=self.registry,
      value=(self.value + other.value)
    )

  def __mul__(self, other: 'CompositeUnit | Self | float | int', /) -> Self:
    if isinstance(other, (float, int)):
      return self * self.registry.dimensionless(other)

    self._check_other_registry(other)

    return Quantity(
      dimensionality=compose_dimensionalities(self.dimensionality, other.dimensionality),
      registry=self.registry,
      value=(self.value * other.value)
    )

  def __truediv__(self, other: 'CompositeUnit | Self | float | int', /) -> Self:
    if isinstance(other, (float, int)):
      return self / self.registry.dimensionless(other)

    self._check_other_registry(other)

    return Quantity(
      dimensionality=compose_dimensionalities(self.dimensionality, other.dimensionality, factor=-1),
      registry=self.registry,
      value=(self.value / other.value)
    )

  def __pow__(self, other: float | int, /):
    return Quantity(
      dimensionality={dimension: (power * other) for dimension, power in self.dimensionality.items()},
      registry=self.registry,
      value=(self.value ** other)
    )

  def format(self, *, style: Literal['long', 'short'] = 'short', system: str = "SI", variants: Optional[dict[str, Any]] = None):
    if not self.dimensionality:
      return f"{self.value:.2f}"

    var_dimension, var_dimension_factor = next(((dimension, factor) for dimension, factor in self.dimensionality.items() if factor >= 1), next(iter(self.dimensionality.items())))

    # output = f"{self.value:.02f} "
    output = str()
    value = self.value

    def unit_matches(dimension: DimensionName, unit: Unit):
      if (unit.dimension != dimension) or not (system in unit.systems):
        return False

      if variants:
        for variant_key, variant_value in variants.items():
          if (variant_key in unit.variants) and (variant_value != unit.variants[variant_key]):
            return False

      return True

    output_units = list[tuple[Unit, float | int]]()

    for dimension, factor in self.dimensionality.items():
      if dimension == var_dimension:
        continue

      unit = next(unit for unit in self.registry._units if unit_matches(dimension, unit))
      value /= unit.value ** factor

      output_units.append((unit, factor))

    has_offset = (len(self.dimensionality) == 1) and (var_dimension_factor == 1.0)

    # print(var_dimension_factor)
    var_dimension_units = list((unit, (value - (unit.offset if has_offset else 0.0)) / unit.value ** var_dimension_factor) for unit in self.registry._units if unit_matches(var_dimension, unit))
    var_dimension_unit, value = sorted([(unit, quant) for unit, quant in var_dimension_units], key=(lambda item: (abs(item[1]) < 1.0, item[1])))[0]
    # pprint(var_dimension_unit)

    output_units.append((var_dimension_unit, var_dimension_factor))

    for index, (unit, factor) in enumerate(sorted(output_units, key=(lambda item: -item[1]))):
      if index > 0:
        output += ("/" if factor < 0 else "*")

      if style == 'short':
        output += unit.short
      if style == 'long':
        output += unit.long

      if abs(factor) != 1:
        output += format_superscript(abs(factor))

    return f"{value:.02f} {output}"


@dataclass(frozen=True)
class CompositeUnit:
  dimensionality: Dimensionality
  registry: 'UnitRegistry' = field(repr=False)
  value: float

  @overload
  def __mul__(self, other: Self, /) -> 'CompositeUnit':
    ...

  @overload
  def __mul__(self, other: Quantity | float | int, /) -> Quantity:
    ...

  def __mul__(self, other: Quantity | Self | float | int, /):
    if isinstance(other, (float, int)):
      return self * self.registry.dimensionless(other)

    if self.registry is not other.registry:
      raise ValueError("Operation with different registries")

    if isinstance(other, CompositeUnit):
      return CompositeUnit(
        dimensionality=compose_dimensionalities(self.dimensionality, other.dimensionality),
        registry=self.registry,
        value=(self.value * other.value)
      )

    return other * self


  @overload
  def __rmul__(self, other: 'CompositeUnit', /) -> 'CompositeUnit':
    ...

  @overload
  def __rmul__(self, other: Quantity | float | int, /) -> Quantity:
    ...

  def __rmul__(self, other:  'CompositeUnit | Quantity | float | int', /):
    return self * other


  @overload
  def __truediv__(self, other: 'CompositeUnit', /) -> 'CompositeUnit':
    ...

  @overload
  def __truediv__(self, other: Quantity | float | int, /) -> Quantity:
    ...

  def __truediv__(self, other: 'CompositeUnit | Quantity | float | int', /):
    if isinstance(other, (float, int)):
      return self / self.registry.dimensionless(other)

    if self.registry is not other.registry:
      raise ValueError("Operation with different registries")

    if isinstance(other, CompositeUnit):
      return CompositeUnit(
        dimensionality=compose_dimensionalities(self.dimensionality, other.dimensionality, factor=-1),
        registry=self.registry,
        value=(self.value / other.value)
      )

    return other / self


  def __pow__(self, other: float | int, /):
    return CompositeUnit(
      dimensionality={dimension: (power * other) for dimension, power in self.dimensionality.items()},
      registry=self.registry,
      value=(self.value ** other)
    )


@final
@dataclass(frozen=True)
class Unit(CompositeUnit):
  dimensionality: Dimensionality
  label: tuple[str, str]
  offset: float
  registry: 'UnitRegistry' = field(repr=False)
  symbol: tuple[str, str]
  systems: set[SystemName]

  @overload
  def __mul__(self, other: Self, /) -> 'CompositeUnit':
    ...

  @overload
  def __mul__(self, other: Quantity | float | int, /) -> Quantity:
    ...

  def __mul__(self, other: Quantity | Self | float | int, /):
    if isinstance(other, (float, int)) and (self.offset != 0.0):
      quantity = super().__mul__(other)

      return Quantity(
        dimensionality=self.dimensionality,
        registry=self.registry,
        value=(quantity.value + self.offset)
      )

    return super().__mul__(other)


class InvalidUnitNameError(Exception):
  pass

@final
class UnitRegistry:
  def __init__(self):
    self._units = list[Unit]()
    self._unit_groups = dict[str, set[Unit]]()
    self._units_by_name = dict[str, Unit]()

  def dimensionless(self, value: float | int, /):
    return Quantity(
      dimensionality=dict(),
      registry=self,
      value=value
    )

  def parse(self, string: str, /):
    from .parser import parse
    return parse(string, self)

  def unit(self, name: str, /):
    if not name in self._units_by_name:
      raise InvalidUnitNameError(f"Invalid unit name: {name}")

    return self._units_by_name[name]

  def __getattribute__(self, name: str, /):
    try:
      return super().__getattribute__(name)
    except AttributeError:
      if name in self._units_by_name:
        return self._units_by_name[name]

      raise


  @classmethod
  def load(cls, file: IO[bytes]):
    data = cast(RegistryData, tomllib.load(file))
    # pprint(data)

    def ensure_tuple(value: str | list[str], /):
      return (value, value) if isinstance(value, str) else (value[0], value[1])

    registry = cls()

    for data_unit in data['units']:
      unit = Unit(
        dimensionality={DimensionName(dimension): power for dimension, power in data_unit['dimensionality'].items()},
        label=ensure_tuple(data_unit['label']),
        symbol=ensure_tuple(data_unit['symbol']),
        offset=data_unit.get('offset', 0.0),
        registry=registry,
        systems={SystemName(system) for system in data_unit.get('systems', ["SI"])},
        value=data_unit.get('value', 1.0)
      )

      for name in [*data_unit.get('label_names', unit.label), *data_unit.get('symbol_names', unit.symbol)]:
        registry._units_by_name[name] = unit

      prefixsys_names = data_unit.get('prefixes', list())

      while prefixsys_names:
        prefixsys_name = prefixsys_names.pop()
        data_prefixsys = data['prefix_systems'][prefixsys_name]

        prefixsys_names += data_prefixsys.get('extend', list())

        for data_prefix in data_prefixsys.get('prefixes', list()):
          prefixed_unit = Unit(
            dimensionality=unit.dimensionality,
            offset=unit.offset,
            label=(data_prefix['label'] + unit.label[0], data_prefix['label'] + unit.label[1]),
            registry=registry,
            symbol=(data_prefix['symbol'] + unit.symbol[0], data_prefix['symbol'] + unit.symbol[1]),
            systems=unit.systems,
            value=(data_prefix['factor'] * unit.value)
          )

          for name in data_unit.get('label_names', unit.label):
            registry._units_by_name[data_prefix['label'] + name] = prefixed_unit

          for name in data_unit.get('symbol_names', unit.symbol):
            registry._units_by_name[data_prefix['symbol'] + name] = prefixed_unit

    return registry


__all__ = [
  'DimensionName',
  'InvalidUnitNameError',
  'Quantity',
  'SystemName',
  'Unit',
  'UnitRegistry'
]
