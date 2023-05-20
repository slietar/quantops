from pathlib import Path
from pprint import pprint


from . import UnitRegistry

ureg = UnitRegistry.load((Path(__file__).parent / "registry.toml").open("rb"))
speed_unit = ureg.unit('B') / ureg.unit('sec') # ** 2
speed1 = 30.0e3 * speed_unit

print(speed1.format(variants={ 'binary_memory': True }))


dist = 3 * ureg.unit('km')
print(dist.format(system='USCS'))


print(speed1 == speed1)
