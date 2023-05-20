# Quantops


```py
from quantops import UnitRegistry

ureg = UnitRegistry()

x = 3.0 * (ureg.µl / ureg.min)
x.format(
  variants=dict(
    system: 'USCS'
  )
)

(3.0 * ureg.MB).format(
  variants=dict(
    memory_mode='binary'
  )
)

(3.0 * ureg.MB / ureg.sec).format(
  variable_dimension=(ureg.sec ** -1)
)
```
