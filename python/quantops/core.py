import functools
import math
import operator
import tomllib
from dataclasses import dataclass, field
from pprint import pprint
from typing import (IO, Any, Generic, Literal, NewType, NotRequired, Optional,
                    Self, TypedDict, TypeVar, cast, final, overload)

from snaptext import LocatedString


K = TypeVar('K')
V = TypeVar('V')

class FrozenDict(dict[K, V], Generic[K, V]):
  def __hash__(self):
    return hash(frozenset(self.items()))

  def __repr__(self):
    return f"{self.__class__.__name__}({super().__repr__()})"


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
ContextName = NewType('ContextName', str)
PrefixSystemName = NewType('PrefixSystemName', str)
SystemName = NewType('SystemName', str)
UnitId = NewType('UnitId', str)

class Dimensionality(FrozenDict[DimensionName, float | int]):
  def __mul__(self, other: Self, /):
    return self.__class__({
      dimension: power for dimension
        in {*self.keys(), *other.keys()}
        if (power := self.get(dimension, 0) + other.get(dimension, 0)) != 0
    })

  def __pow__(self, other: float | int, /):
    return self.__class__({
      dimension: new_power for dimension, power in self.items() if (new_power := power * other) != 0
    })

  def __truediv__(self, other: Self, /):
    return self * (other ** -1)


class RegistryContextVariantData(TypedDict):
  options: list[str]
  systems: list[SystemName]

class RegistryContextData(TypedDict):
  name: ContextName
  variants: list[RegistryContextVariantData]

class RegistryPrefixData(TypedDict):
  factor: float
  label: str
  symbol: str
  symbol_names: NotRequired[list[str]]

class RegistryPrefixSystemData(TypedDict):
  name: PrefixSystemName
  extend: NotRequired[list[PrefixSystemName]]
  prefixes: NotRequired[list[RegistryPrefixData]]

class RegistryUnitData(TypedDict):
  dimensionality: Dimensionality
  label: str | list[str]
  label_names: NotRequired[list[str]]
  symbol: str | list[str]
  symbol_names: NotRequired[list[str]]

  prefixes: NotRequired[list[PrefixSystemName]]

  offset: NotRequired[float]
  value: NotRequired[float]

class RegistryData(TypedDict):
  contexts: list[RegistryContextData]
  prefix_systems: list[RegistryPrefixSystemData]
  units: list[RegistryUnitData]


def format_superscript(number: float | int, /):
  return str().join(SUPERSCRIPT_CHARS[digit] for digit in str(number))

def format_assembly(assembly: 'ConstantUnitAssembly', *, style: Literal['label', 'symbol']):
    output = str()

    for index, part in enumerate(assembly):
      if index > 0:
        output += ("/" if part.power < 0 else "*")

      plural = (index < 1) and (part.power > 0)

      if style == 'label':
        output += part.unit.label[1 if plural else 0]
      if style == 'symbol':
        output += part.unit.symbol[1 if plural else 0]

      if (part.power != 1) and ((index < 1) or (part.power != -1)):
        output += format_superscript(abs(part.power) if (index > 0) else part.power)

    return output

def format_quantity(value: float, resolution: float, option: 'ContextVariantOption', *, style: Literal['label', 'symbol']):
  decimal_count = max(0, math.ceil(-math.log10(resolution / option.value))) if (resolution > 0) else None
  output = str()

  if value < 0:
    output += '-'

  output += format(abs(value / option.value), f".{decimal_count}f" if (decimal_count is not None) else "e")

  if option.assembly:
    assembled = format_assembly(option.assembly, style=style)

    if not assembled.startswith("°"):
      output += " "

    output += assembled

  return output


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
      dimensionality=(self.dimensionality * other.dimensionality),
      registry=self.registry,
      value=(self.value * other.value)
    )

  def __truediv__(self, other: 'CompositeUnit | Self | float | int', /) -> Self:
    if isinstance(other, (float, int)):
      return self / self.registry.dimensionless(other)

    self._check_other_registry(other)

    return Quantity(
      dimensionality=(self.dimensionality / other.dimensionality),
      registry=self.registry,
      value=(self.value / other.value)
    )

  def __pow__(self, other: float | int, /):
    return Quantity(
      dimensionality=Dimensionality({ dimension: (power * other) for dimension, power in self.dimensionality.items() }),
      registry=self.registry,
      value=(self.value ** other)
    )

  def format(
      self,
      context_name: ContextName | str,
      resolution: float = 0.0,
      *,
      style: Literal['label', 'symbol'] = 'symbol',
      system: SystemName = SystemName("SI")
    ):
    context = self.registry._contexts[context_name]

    if self.dimensionality != context.dimensionality:
      raise ValueError("Dimensionality mismatch")

    variant = next(variant for variant in context.variants if system in variant.systems)

    def order(option: ContextVariantOption):
      value = self.value / option.value
      return (value < 1, value * (1 if value > 1 else -1))

    option = sorted([option for option in variant.options], key=order)[0] if math.isfinite(self.value) else variant.options[0]
    return format_quantity(self.value, resolution, option, style=style)

  def __repr__(self):
    assembly = ConstantUnitAssembly()

    for dimension, power in self.dimensionality.items():
      unit = next(unit for unit in self.registry._units_by_name.values() if (unit.dimensionality == Dimensionality({ dimension: 1 })) and (unit.offset == 0.0) and (unit.value == 1.0))
      assembly.append(UnitAssemblyConstantPart(unit, power))

    assembly = sorted(assembly, key=(lambda part: -part.power))
    quantity = format_quantity(self.value, 0.0, ContextVariantOption(assembly, 1.0), style='symbol')

    return f"{self.__class__.__name__}({quantity!r})"


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
        dimensionality=(self.dimensionality * other.dimensionality),
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
        dimensionality=(self.dimensionality / other.dimensionality),
        registry=self.registry,
        value=(self.value / other.value)
      )

    return other / self


  def __pow__(self, other: float | int, /):
    return CompositeUnit(
      dimensionality=Dimensionality({ dimension: (power * other) for dimension, power in self.dimensionality.items() }),
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

  @property
  def id(self):
    return UnitId(self.symbol[0])

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

  def __repr__(self):
    return f"{self.__class__.__name__}({self.symbol[0]!r})"

class InvalidUnitNameError(Exception):
  pass

@dataclass(frozen=True)
class UnitAssemblyConstantPart:
  unit: Unit
  power: float

@dataclass(frozen=True)
class UnitAssemblyVariablePart:
  units: frozenset[Unit]
  power: float

@dataclass(frozen=True)
class UnitAssembly:
  after_variable_parts: list[UnitAssemblyConstantPart]
  before_variable_parts: list[UnitAssemblyConstantPart]
  variable_part: Optional[UnitAssemblyVariablePart]

ConstantUnitAssembly = list[UnitAssemblyConstantPart]

@dataclass(frozen=True)
class ContextVariantOption:
  assembly: ConstantUnitAssembly
  value: float

@dataclass(frozen=True)
class ContextVariant:
  options: list[ContextVariantOption]
  systems: set[SystemName]

@dataclass(frozen=True)
class Context:
  dimensionality: Dimensionality
  variants: list[ContextVariant]


@final
class UnitRegistry:
  def __init__(self):
    self._contexts = dict[str, Context]()
    self._unit_groups = dict[str, set[Unit]]()
    self._units_by_id = dict[UnitId, Unit]()
    self._units_by_name = dict[str, Unit]()

  def dimensionless(self, value: float | int, /):
    return Quantity(
      dimensionality=Dimensionality(),
      registry=self,
      value=value
    )

  def parse_assembly(self, string: str, /):
    from .parser import parse_assembly
    return parse_assembly(string, self)

  def parse_quantity(self, string: str, /):
    from .parser import tokenize

    walker = tokenize(LocatedString(string), self)
    return walker.expect_only(walker.accept_quantity())

  def serialize(self):
    return {
      "contexts": {
        context_name: {
          "variants": [
            {
              "options": [
                {
                  "assembly": [[part.unit.id, part.power] for part in option.assembly],
                  "value": option.value
                } for option in variant.options
              ],
              "systems": list(variant.systems)
            } for variant in context.variants
          ]
        } for context_name, context in self._contexts.items()
      },
      "units": {
        unit.id: {
          "label": list(unit.label),
          "symbol": list(unit.symbol),
          "value": unit.value
        } for unit in self._units_by_id.values()
      }
    }

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
    from .parser import parse_assembly

    data = cast(RegistryData, tomllib.load(file))
    # pprint(data)

    def ensure_tuple(value: str | list[str], /):
      return (value, value) if isinstance(value, str) else (value[0], value[1])

    registry = cls()

    data_prefix_systems = {
      data_prefix_system['name']: data_prefix_system for data_prefix_system in data['prefix_systems']
    }

    for data_unit in data['units']:
      unit = Unit(
        dimensionality=Dimensionality({ DimensionName(dimension): power for dimension, power in data_unit['dimensionality'].items() }),
        label=ensure_tuple(data_unit['label']),
        symbol=ensure_tuple(data_unit['symbol']),
        offset=data_unit.get('offset', 0.0),
        registry=registry,
        value=data_unit.get('value', 1.0)
      )

      registry._units_by_id[unit.id] = unit

      for name in [*data_unit.get('label_names', unit.label), *data_unit.get('symbol_names', unit.symbol)]:
        registry._units_by_name[name] = unit

      all_units = {unit}
      prefixsys_names = data_unit.get('prefixes', list())

      while prefixsys_names:
        prefixsys_name = prefixsys_names.pop()
        data_prefix_system = data_prefix_systems[prefixsys_name]

        prefixsys_names += data_prefix_system.get('extend', list())

        for data_prefix in data_prefix_system.get('prefixes', list()):
          prefixed_unit = Unit(
            dimensionality=unit.dimensionality,
            offset=unit.offset,
            label=(data_prefix['label'] + unit.label[0], data_prefix['label'] + unit.label[1]),
            registry=registry,
            symbol=(data_prefix['symbol'] + unit.symbol[0], data_prefix['symbol'] + unit.symbol[1]),
            value=(data_prefix['factor'] * unit.value)
          )

          registry._units_by_id[prefixed_unit.id] = prefixed_unit

          for name in data_unit.get('label_names', unit.label):
            registry._units_by_name[data_prefix['label'] + name] = prefixed_unit

          for symbol_name in data_unit.get('symbol_names', unit.symbol):
            for prefix_name in data_prefix.get('symbol_names', [data_prefix['symbol']]):
              registry._units_by_name[prefix_name + symbol_name] = prefixed_unit

          all_units.add(prefixed_unit)

      if len(unit.dimensionality) == 1:
        dimension_name, dimension_factor = next(iter(unit.dimensionality.items()))

        if dimension_factor == 1:
          registry._unit_groups.setdefault(dimension_name, set()).update(all_units)

      registry._unit_groups[unit.symbol[0]] = all_units

    for data_context in data['contexts']:
      context_dimensionality: Optional[Dimensionality] = None
      variants = list[ContextVariant]()

      for data_variant in data_context['variants']:
        option_assemblies = list[ConstantUnitAssembly]()

        for data_option in data_variant['options']:
          assembly, option_dimensionality = parse_assembly(data_option, registry)

          if context_dimensionality is None:
            context_dimensionality = option_dimensionality
          elif context_dimensionality != option_dimensionality:
            raise ValueError("Invalid dimensionality")

          if assembly.variable_part:
            option_assemblies += [[*assembly.before_variable_parts, UnitAssemblyConstantPart(unit, assembly.variable_part.power), *assembly.after_variable_parts] for unit in assembly.variable_part.units]
          else:
            option_assemblies.append(assembly.before_variable_parts)

        options = [ContextVariantOption(
          option_assembly,
          functools.reduce(operator.mul, [part.unit.value ** part.power for part in option_assembly])
        ) for option_assembly in option_assemblies]

        variants.append(ContextVariant(options, systems=set(data_variant['systems'])))

      if context_dimensionality is None:
        continue

      registry._contexts[data_context['name']] = Context(context_dimensionality, variants)

    return registry


__all__ = [
  'DimensionName',
  'InvalidUnitNameError',
  'PrefixSystemName',
  'Quantity',
  'SystemName',
  'Unit',
  'UnitRegistry'
]
