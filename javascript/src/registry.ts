import { ReactNode } from 'react';

import defaultRegistryData from '../data/registry.json';
import { ConstantAssembly, ContextName, ContextVariant, ContextVariantOption, Data, SystemName } from './data.js';


export type CreateElementType<T> = (tag: string, attributes: Record<string, any> | null | undefined, ...children: ReactNode[]) => T;

export class UnitRegistry {
  data: Data;

  constructor(data: Data = defaultRegistryData) {
    this.data = data;
  }

  filterRangeCompositeUnitFormats(min: number, max: number, options: { context: ContextName; system: SystemName; }) {
    let variant = this.findVariant(options);
    let minOption = this.findBestVariantOption(min, variant);
    let maxOption = this.findBestVariantOption(max, variant);

    let sortedOptions = variant.options.slice().sort((a, b) => (b.value - a.value));

    return sortedOptions.slice(
      sortedOptions.indexOf(minOption),
      sortedOptions.indexOf(maxOption) + 1
    );
  }

  findBestVariantOption(value: number, variant: ContextVariant) {
    return variant.options.slice().sort((a, b) => {
      let aValue = value / a.value;
      let bValue = value / b.value;

      let bool = (v: boolean) => v ? 1 : -1;
      return (bool(aValue < 1) - bool(bValue < 1)) || (aValue - bValue) * bool(aValue > 1);
    })[0];
  }

  findVariant(options: { context: ContextName; system: SystemName; }) {
    let context = this.data.contexts[options.context];
    return context.variants.find((variant) => variant.systems.includes(options.system))!;
  }

  formatQuantityAsReact<T>(value: number, resolution: number, option: ContextVariantOption, options: {
    createElement: CreateElementType<T>;
    skipUnit?: boolean;
  }) {
    return [
      ...this.formatMagnitudeAsReact(value / option.value, resolution / option.value),
      ...(!options.skipUnit && (option.assembly.length > 0)
        ? [
          '&nbsp;',
          ...this.formatAssemblyAsReact(option.assembly, { createElement: options.createElement })
        ]
        : [])
    ];
  }

  formatAssemblyAsReact<T>(assembly: ConstantAssembly, options: {
    createElement: CreateElementType<T>;
    style?: 'label' | 'symbol';
  }) {
    let output: (T | string)[] = [];

    for (let [index, [unitId, power]] of assembly.entries()) {
      let unit = this.data.units[unitId];

      if (index > 0) {
        output.push((power < 0 ? '/' : '&middot;'));
      }

      let plural = (index < 1) && (power > 0);

      switch (options.style ?? 'symbol') {
        case 'label':
          output.push(plural ? unit.label[1] : unit.label[0]);
          break;
        case 'symbol':
          output.push(plural ? unit.symbol[1] : unit.symbol[0]);
          break;
      }

      if ((power !== 1) && ((index < 1) || (power !== -1))) {
        output.push(options.createElement('sup', {},
          (index > 0 ? Math.abs(power) : power).toString()
        ));
      }
    }

    return output;
  }

  formatMagnitudeAsReact(value: number, resolution: number) {
    let decimalCount = Math.max(0, Math.ceil(-Math.log10(resolution)));

    return [
      ...(value < 0 ? ['&ndash;'] : []),
      Math.abs(value).toFixed(isFinite(decimalCount) ? decimalCount : 0)
    ];
  }

  formatRangeAsReact<T>(min: number, max: number, resolution: number, minOption: ContextVariantOption, maxOption: ContextVariantOption, options: { createElement: CreateElementType<T>; }) {
    return [
      ...this.formatQuantityAsReact(min, resolution, minOption, { ...options, skipUnit: (maxOption === minOption) }),
      ' &mdash; ',
      ...this.formatQuantityAsReact(max, resolution, maxOption, options)
    ];
  }
}


let ureg = new UnitRegistry();

let value = 0.5;
let variant = ureg.findVariant({ context: 'velocity', system: 'SI' });
let option = ureg.findBestVariantOption(value, variant);

console.log(ureg.formatQuantityAsReact(value, 0.1, option, {
  createElement: (...args) => args
}));

console.log(ureg.formatRangeAsReact(2.0, 5000.0, 0.,
  ureg.findBestVariantOption(2.0, variant),
  ureg.findBestVariantOption(5000.0, variant),
  { createElement: (...args) => args }
));
