from importlib.resources import files
from pprint import pprint

from .core import UnitRegistry


ureg = UnitRegistry.load(files("quantops").joinpath("registry.toml").open("rb"))


print(ureg.parse('3 m/N'))
