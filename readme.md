# Quantops

**Quantops** is a project that provides tools to define, manipulate and format physical quantities. It comprises both a Python and JavaScript library, and allows for seamless serialization between the two.


## Installation

```sh
# Python
$ pip install quantops

# JavaScript
$ npm install quantops
```


## Usage

### In Python

```py
from quantops import UnitRegistry

ureg = UnitRegistry.load_default()


x = 0.003 * ureg.meter
x.format('length', resolution=(0.00001 * ureg.meter))
# => 300.0 mm

x.format('length', system='imperial')
# => ...

y = 50 * ureg.ug / ureg.ml
y.format('dna_concentration')
# => 50 ng/µl

z = 30 * ureg.m / ureg.s
z.format('car_velocity')
# => 108 km/h
```

```py
# Custom contexts

flowrate_context = Context({
  'SI': ['~l/min', 'm^3/s'],
  'imperial': ['~gal/min', 'ft^3/s'],
  'US': ['~gal/min', 'ft^3/s']
})

x = 30 * ureg.l / ureg.s
x.format(flowrate_context, system='imperial')
```

```py
serialized = x.serialize()
# => Opaque JSON-serializable object
```

### In JavaScript

```js
import { UnitRegistry } from 'quantops';

let ureg = new UnitRegistry();
let x = ureg.load(serialized); // Transferred rom above

x.format('length', { resolution: 0.00001 * ureg.meter });
```
