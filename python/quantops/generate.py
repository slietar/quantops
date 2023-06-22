import json
import sys

from .core import UnitRegistry


ureg = UnitRegistry.get_default()
json.dump(ureg.serialize(), sys.stdout, separators=(',', ':'))
