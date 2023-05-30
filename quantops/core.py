import functools
from pprint import pprint
import tomllib
from dataclasses import dataclass, field
from typing import IO, Any, Generic, Literal, NewType, NotRequired, Optional, Protocol, Required, Self, TypeVar, TypedDict, cast, final, overload, reveal_type


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
PrefixSystemName = NewType('PrefixSystemName', str)
SystemName = NewType('SystemName', str)

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


class RegistryPrefixData(TypedDict):
  factor: float
  label: str
  symbol: str
  symbol_names: NotRequired[list[str]]

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
  assemblies: list[dict[str, Any]]
  prefix_systems: dict[PrefixSystemName, RegistryPrefixSystemData]
  units: list[RegistryUnitData]

def compose_dimensionalities(a: Dimensionality, b: Dimensionality, /, factor: int = 1):
  return Dimensionality({
    dimension: power for dimension
      in {*a.keys(), *b.keys()}
      if (power := a.get(dimension, 0) + b.get(dimension, 0) * factor) != 0
  })

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
      dimensionality=Dimensionality({ dimension: (power * other) for dimension, power in self.dimensionality.items() }),
      registry=self.registry,
      value=(self.value ** other)
    )

  def format(self, assembly_name: str, *, style: Literal['label', 'symbol'] = 'symbol', system: SystemName = SystemName("SI")):
    assembly = self.registry._assemblies[assembly_name]
    # print(assembly)
    # return

    if self.dimensionality != assembly.dimensionality:
      raise ValueError("Dimensionality mismatch")

    output = str()
    value = self.value

    def unit_matches(unit: Unit):
      return (system in unit.systems)

    # output_units = list[tuple[Unit, float]]()

    FactoredUnit = tuple[Unit, float]
    hypotheses = list[tuple[list[FactoredUnit], float]]()

    for option in assembly.options:
      option_components = list[FactoredUnit]()
      option_value = self.value

      for component_index, (component_units, component_factor) in enumerate(option.components):
        matching_unit = next((unit for unit in component_units if unit_matches(unit)), None)

        if matching_unit is None:
          # TODO: Fix
          raise RuntimeError

        if component_index == option.variable_index:
          continue

        option_components.append((matching_unit, component_factor))
        option_value /= matching_unit.value ** component_factor

      if option.variable_index is not None:
        var_component_units, var_component_factor = option.components[option.variable_index]
        has_offset = False
        var_component_units = list((unit, (option_value - (unit.offset if has_offset else 0.0)) / unit.value ** var_component_factor) for unit in var_component_units if unit_matches(unit))
        var_component_unit, option_value = sorted([(unit, quant) for unit, quant in var_component_units], key=(lambda item: (abs(item[1]) < 1.0, item[1])))[0]

        hypotheses.append(([
          *option_components[0:option.variable_index],
          (var_component_unit, var_component_factor),
          *option_components[option.variable_index:],
        ], option_value))
      else:
        hypotheses.append((option_components, option_value))

    print(">", hypotheses)
    factored_units, value = sorted([(components, value) for components, value in hypotheses], key=(lambda item: (abs(item[1]) < 1.0, item[1])))[0]

    # has_offset = (len(self.dimensionality) == 1) and (var_dimension_factor == 1.0)

    for index, (unit, factor) in enumerate(factored_units):
      if index > 0:
        output += ("/" if factor < 0 else "*")

      plural = (index < 1) and (factor > 0)

      if style == 'label':
        output += unit.label[1 if plural else 0]
      if style == 'symbol':
        output += unit.symbol[1 if plural else 0]

      if (factor != 1) and ((index < 1) or (factor != -1)):
        output += format_superscript(abs(factor) if (index > 0) else factor)

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
  systems: frozenset[SystemName]

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

# X = tuple[set[Unit], int]
# UnitAssembly = list[list[set[Unit]]]

@dataclass
class UnitAssemblyOption:
  components: 'tuple[tuple[frozenset[Unit], int], ...]'
  variable_index: Optional[int]

@dataclass
class UnitAssembly:
  dimensionality: Dimensionality
  options: list[UnitAssemblyOption]


@final
class UnitRegistry:
  def __init__(self):
    self._assemblies = dict[str, UnitAssembly]()
    self._units = list[Unit]()
    self._unit_groups = dict[str, set[Unit]]()
    self._units_by_name = dict[str, Unit]()

  def dimensionless(self, value: float | int, /):
    return Quantity(
      dimensionality=Dimensionality(),
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
    from .parser import parse_assembly

    data = cast(RegistryData, tomllib.load(file))
    # pprint(data)

    def ensure_tuple(value: str | list[str], /):
      return (value, value) if isinstance(value, str) else (value[0], value[1])

    registry = cls()

    for data_unit in data['units']:
      unit = Unit(
        dimensionality=Dimensionality({ DimensionName(dimension): power for dimension, power in data_unit['dimensionality'].items() }),
        label=ensure_tuple(data_unit['label']),
        symbol=ensure_tuple(data_unit['symbol']),
        offset=data_unit.get('offset', 0.0),
        registry=registry,
        systems=frozenset({SystemName(system) for system in data_unit.get('systems', ["SI"])}),
        value=data_unit.get('value', 1.0)
      )

      for name in [*data_unit.get('label_names', unit.label), *data_unit.get('symbol_names', unit.symbol)]:
        registry._units_by_name[name] = unit

      all_units = {unit}
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

          for symbol_name in data_unit.get('symbol_names', unit.symbol):
            for prefix_name in data_prefix.get('symbol_names', [data_prefix['symbol']]):
              registry._units_by_name[prefix_name + symbol_name] = prefixed_unit

          all_units.add(prefixed_unit)

      if len(unit.dimensionality) == 1:
        dimension_name, dimension_factor = next(iter(unit.dimensionality.items()))

        if dimension_factor == 1:
          registry._unit_groups.setdefault(dimension_name, set()).update(all_units)

      registry._unit_groups[unit.symbol[0]] = all_units

    for data_assembly in data['assemblies']:
      dimensionality: Optional[Dimensionality] = None
      options = list[UnitAssemblyOption]()

      for data_option in data_assembly['options']:
        option, option_dimensionality = parse_assembly(data_option, registry)

        if dimensionality is None:
          dimensionality = option_dimensionality
        elif dimensionality != option_dimensionality:
          raise ValueError("Invalid dimensionality")

        options.append(option)

      if dimensionality is None:
        continue

      registry._assemblies[data_assembly['name']] = UnitAssembly(dimensionality, options)

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
