import json
from pathlib import Path

from .core import UnitRegistry


ureg = UnitRegistry.load_default()

data_path = Path(__file__).parent / "../../javascript/data/registry.json"
data_path.parent.mkdir(exist_ok=True, parents=True)

with data_path.open("w") as file:
  json.dump(ureg.serialize(), file, separators=(',', ':'))
