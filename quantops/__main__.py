from importlib.resources import files
from pprint import pprint

from .parser import ParserError

from .core import UnitRegistry


ureg = UnitRegistry.load(files("quantops").joinpath("registry.toml").open("rb"))


try:
  print(ureg.parse(' 3 s - 5 m'))
except ParserError as e:
  print(e.message)
  print(e.area)
  print(e.area.format())
