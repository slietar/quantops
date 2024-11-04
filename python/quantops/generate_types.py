from .core import AtomicUnit, UnitRegistry


def generate_types(name: str, ureg: UnitRegistry):
  output = f'from {UnitRegistry.__module__} import {AtomicUnit.__name__}, {UnitRegistry.__name__}\n\n'
  output += f'class {name}({UnitRegistry.__name__}):\n'

  for name in ureg._units_by_name.keys():
    output += f'  {name}: {AtomicUnit.__name__}\n'

  output += '\n\n'


  for extent in ureg._extents_by_dimensionality.values():
    output += f'class {extent.quantity_symbol}:\n'
    output += f'  def __add__(self, other: {extent.quantity_symbol}) -> {extent.quantity_symbol}:\n    ...\n\n'

    output += f'  @overload\n'
    output += f'  def __mul__(self, other: float) -> {extent.quantity_symbol}:\n    ...\n\n'

    for other_extent in ureg._extents_by_dimensionality.values():
      cross_dimensionality = extent.value * other_extent.value
      cross_extent = ureg._extents_by_dimensionality.get(cross_dimensionality)

      if cross_extent:
        output += f'  @overload\n'
        output += f'  def __mul__(self, other: {other_extent.quantity_symbol}) -> {cross_extent.quantity_symbol}:\n    ...\n\n'


  return output


# x = generate_types('DefaultRegistry', UnitRegistry.load_default())
# print(x)
