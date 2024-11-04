import functools
import operator
import tomllib
from typing import IO, NotRequired, Optional, TypedDict, cast

from snaptext import LocatedString

from .core import (AtomicUnit, ConstantUnitAssembly, Context, ContextName,
                   ContextVariant, ContextVariantOption, Dimensionality,
                   DimensionName, ExtentName, Extent, SystemName,
                   UnitAssemblyConstantPart)


class RegistryContextVariantData(TypedDict):
  options: list[str]
  systems: NotRequired[list[str]]

class RegistryContextData(TypedDict):
  name: str
  variants: list[RegistryContextVariantData]

class RegistryDimensionalityData(TypedDict):
  name: str
  value: dict[str, int]

class RegistryPrefixData(TypedDict):
  factor: float
  label: str
  symbol: str
  symbol_names: NotRequired[list[str]]

class RegistryPrefixSystemData(TypedDict):
  name: str
  extend: NotRequired[list[str]]
  prefixes: NotRequired[list[RegistryPrefixData]]

class RegistryUnitData(TypedDict):
  dimensionality: dict[str, int]
  label: str | list[str]
  label_names: NotRequired[list[str]]
  symbol: str | list[str]
  symbol_names: NotRequired[list[str]]

  prefixes: NotRequired[list[str]]

  offset: NotRequired[float]
  value: NotRequired[float]

class RegistryData(TypedDict):
  contexts: list[RegistryContextData]
  dimensionalities: list[RegistryDimensionalityData]
  prefix_systems: list[RegistryPrefixSystemData]
  units: list[RegistryUnitData]


def load_dimensionality(data: dict[str, int], /):
  return Dimensionality({ DimensionName(dimension): power for dimension, power in data.items() })


def load(cls, file: IO[bytes], /):
  from .parser import tokenize

  data = cast(RegistryData, tomllib.load(file))
  # pprint(data)

  def ensure_tuple(value: str | list[str], /):
    return (value, value) if isinstance(value, str) else (value[0], value[1])

  registry = cls()

  data_prefix_systems = {
    data_prefix_system['name']: data_prefix_system for data_prefix_system in data['prefix_systems']
  }

  for data_unit in data['units']:
    unit_symbol = ensure_tuple(data_unit['symbol'])
    unit = AtomicUnit(
      dimensionality=load_dimensionality(data_unit['dimensionality']),
      label=ensure_tuple(data_unit['label']),
      symbol=unit_symbol,
      offset=data_unit.get('offset', 0.0),
      registry=registry,
      value=data_unit.get('value', 1.0)
    )

    registry._units_by_id[unit.id] = unit

    for name in [*data_unit.get('label_names', unit.label), *data_unit.get('symbol_names', unit_symbol)]:
      registry._units_by_name[name] = unit

    all_units = {unit}
    prefixsys_names = data_unit.get('prefixes', list())

    while prefixsys_names:
      prefixsys_name = prefixsys_names.pop()
      data_prefix_system = data_prefix_systems[prefixsys_name]

      prefixsys_names += data_prefix_system.get('extend', list())

      for data_prefix in data_prefix_system.get('prefixes', list()):
        prefixed_unit = AtomicUnit(
          dimensionality=unit.dimensionality,
          offset=unit.offset,
          label=(data_prefix['label'] + unit.label[0], data_prefix['label'] + unit.label[1]),
          registry=registry,
          symbol=(data_prefix['symbol'] + unit_symbol[0], data_prefix['symbol'] + unit_symbol[1]),
          value=(data_prefix['factor'] * unit.value)
        )

        registry._units_by_id[prefixed_unit.id] = prefixed_unit

        for name in data_unit.get('label_names', unit.label):
          registry._units_by_name[data_prefix['label'] + name] = prefixed_unit

        for symbol_name in data_unit.get('symbol_names', unit_symbol):
          for prefix_name in data_prefix.get('symbol_names', [data_prefix['symbol']]):
            registry._units_by_name[prefix_name + symbol_name] = prefixed_unit

        all_units.add(prefixed_unit)

    if len(unit.dimensionality) == 1:
      dimension_name, dimension_factor = next(iter(unit.dimensionality.items()))

      if dimension_factor == 1:
        registry._unit_groups.setdefault(dimension_name, set()).update(all_units)

    registry._unit_groups[unit_symbol[0]] = all_units

  for data_context in data['contexts']:
    context_dimensionality: Optional[Dimensionality] = None
    variants = list[ContextVariant]()

    for data_variant in data_context['variants']:
      option_assemblies = list[ConstantUnitAssembly]()

      for data_option in data_variant['options']:
        walker = tokenize(LocatedString(data_option), registry)
        assembly, option_dimensionality = walker.expect_only(walker.accept_assembly())

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

      variants.append(ContextVariant(options, systems={ SystemName(name) for name in data_variant.get('systems', [SystemName("SI")]) }))

    if context_dimensionality is None:
      continue

    context_name = ContextName(data_context['name'])
    registry._contexts[context_name] = Context(context_dimensionality, variants, name=context_name)

  for data_dimensionality in data['dimensionalities']:
    dimensionality = load_dimensionality(data_dimensionality['value'])
    name = ExtentName(data_dimensionality['name'])

    if name in registry._extents_by_name:
      raise ValueError("Duplicate dimensionality name")

    if dimensionality in registry._extents_by_dimensionality:
      raise ValueError("Duplicate dimensionality")

    dim = Extent(name, dimensionality)
    registry._extents_by_dimensionality[dimensionality] = dim
    registry._extents_by_name[name] = dim


  return registry
