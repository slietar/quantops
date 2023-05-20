from pathlib import Path
from pprint import pprint


from . import UnitRegistry

ureg = UnitRegistry.load((Path(__file__).parent / "registry.toml").open("rb"))
speed_unit = ureg.unit('B') / ureg.unit('s') # ** 2
speed1 = 30.0e3 * speed_unit


temp1 = 100 * (ureg.unit('degC') / ureg.unit('s'))
# print(temp1)


print(temp1.format())
print(temp1.format(variants={ 'temperature': 'kelvin' }))
print(temp1.format(variants={ 'temperature': 'celsius' }))
print(temp1.format(variants={ 'temperature': 'fahrenheit' }))
