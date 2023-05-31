from importlib.resources import files
import json
from pathlib import Path
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


# x = ureg.parse_quantity('10.8 m/s')
# print(x.format('velocity'))

# pprint(ureg.serialize())


data_path = Path(__file__).parent / "../../javascript/data/registry.json"
data_path.parent.mkdir(exist_ok=True, parents=True)

with data_path.open("w") as file:
  json.dump(ureg.serialize(), file, indent=2)
