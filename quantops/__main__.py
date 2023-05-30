from importlib.resources import files
from pprint import pprint

from .core import UnitRegistry
from .parser import ParserError


ureg = UnitRegistry.load(files("quantops").joinpath("registry.toml").open("rb"))

# pprint(ureg._unit_groups)
# pprint(ureg._assemblies)
# pprint(ureg._units_by_name)

# try:
#   print(ureg.parse('~meter/s**2'))
# except ParserError as e:
#   print(e.message)
#   print(e.area)
#   print(e.area.format())


x = ureg.parse('0.10 µl/s')
print(x.format('flowrate'))
