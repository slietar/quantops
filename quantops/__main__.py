from importlib.resources import files
from pprint import pprint

from .core import UnitRegistry


ureg = UnitRegistry.load(files("quantops").joinpath("registry.toml").open("rb"))
speed_unit = ureg.unit('B') / ureg.unit('s') # ** 2
speed1 = 30.0e3 * speed_unit


# temp1 = 100 * (ureg.unit('degC') / ureg.unit('s'))
# print(temp1)


# print(temp1.format())
# print(temp1.format(variants={ 'temperature': 'kelvin' }))
# print(temp1.format(variants={ 'temperature': 'celsius' }))
# print(temp1.format(variants={ 'temperature': 'fahrenheit' }))


x = 30.0 * ureg.unit('µl') / ureg.unit('min')

print(x.format())
