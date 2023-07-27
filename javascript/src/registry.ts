import defaultRegistryData from '../data/registry.json';
import { ConstantAssembly, Context, ContextName, ContextVariant, ContextVariantOption, Data, SystemName } from './data.js';


const SUPERSCRIPT_CHARS: Record<string, string> = {
  '0': '\u2070',
  '1': '\u00b9',
  '2': '\u00b2',
  '3': '\u00b3',
  '4': '\u2074',
  '5': '\u2075',
  '6': '\u2076',
  '7': '\u2077',
  '8': '\u2078',
  '9': '\u2079',
  '+': '\u207a',
  '-': '\u207b'
};

export function formatSuperscript(value: number, options?: { sign?: unknown; }) {
  return (((value < 0)
    ? '-'
    : ((options?.sign && (value > 0))
      ? '+'
      : '')
  ) + Math.abs(value).toString()).split('').map((char) => SUPERSCRIPT_CHARS[char]).join('');
}


export type SerializedContext = {
  type: 'known';
  name: ContextName;
} | {
  type: 'anonymous';
  value: Context;
};

export type CreateElementType<T> = (tag: string, attributes: Record<string, any> | null | undefined, ...children: Node<T>[]) => Node<T>;
export type Node<T> = Iterable<Node<T>> | T | string;

export class UnitRegistry {
  data: Data;

  constructor(data: Data = defaultRegistryData) {
    this.data = data;
  }

  applyOption(value: number, option: ContextVariantOption) {
    return value * option.value + this.getOptionOffset(option);
  }

  applyResolutionToBound(value: number, resolution: number) {
    return value + resolution * (value > 0 ? 1 : -1);
  }

  getContext(context: Context | string) {
    return (typeof context === 'string')
      ? this.data.contexts[context]
      : context;
  }

  getOptionOffset(option: ContextVariantOption) {
    return (option.assembly.length === 1)
      ? this.data.units[option.assembly[0][0]].offset
      : 0;
  }

  deserializeContext(serializedContext: SerializedContext) {
    switch (serializedContext.type) {
      case 'known':
        return this.data.contexts[serializedContext.name];
      case 'anonymous':
        return serializedContext.value;
    }
  }

  filterRangeCompositeUnitFormats(min: number, max: number, context: Context, options: {
    resolution?: number;
    system: SystemName;
  }) {
    let variant = this.findVariant(context, { system: options.system });
    let minOption = this.findBestVariantOption(this.applyResolutionToBound(min, options.resolution ?? 0), variant);
    let maxOption = this.findBestVariantOption(this.applyResolutionToBound(min, options.resolution ?? 0), variant);

    let sortedOptions = variant.options.slice().sort((a, b) => (a.value - b.value));
    let maxOptionIndex = sortedOptions.indexOf(maxOption);

    return sortedOptions.slice(
      // Necessary for cases where the max option is greater than min, e.g. because min is 0
      Math.min(
        sortedOptions.indexOf(minOption),
        maxOptionIndex
      ),
      maxOptionIndex + 1
    );
  }

  findBestVariantOption(value: number, variant: ContextVariant) {
    return variant.options.slice().sort((a, b) => {
      let aValue = Math.abs(value / a.value);
      let bValue = Math.abs(value / b.value);

      let bool = (v: boolean) => v ? 1 : -1;

      // Prefer:
      // 1. Values more than 1
      // 2. If more than 1: low values
      //    If less than 1: high values
      // 3. If both values are equal, because value is 0: low values
      return (bool(aValue < 1) - bool(bValue < 1)) || (aValue - bValue) * bool(aValue > 1) || (a.value - b.value);
    })[0];
  }

  findVariant(context: Context, options: { system: SystemName; }) {
    return context.variants.find((variant) => variant.systems.includes(options.system))!;
  }

  formatQuantityAsReact<T>(value: number, resolution: number, context: Context | string, options: {
    createElement: CreateElementType<T>;
    sign?: unknown;
    style?: 'label' | 'symbol';
  }) {
    let variant = this.findVariant(this.getContext(context), { system: 'SI' });
    let option = this.findBestVariantOption(value, variant);

    return this.formatQuantityWithContextAsReact(value, resolution, option, options);
  }

  formatQuantityWithContextAsReact<T>(value: number, resolution: number, option: ContextVariantOption, options: {
    createElement: CreateElementType<T>;
    sign?: unknown;
    skipUnit?: boolean;
    style?: 'label' | 'symbol';
  }): [string, Node<T>, Node<T>] & Node<T> {
    return [
      this.formatMagnitude(value, resolution, option, { sign: options.sign }),
      ...(!options.skipUnit && (option.assembly.length > 0)
        ? this.formatAssemblyAndGlueAsReact(option.assembly, {
          createElement: options.createElement,
          style: options.style
        })
        : [[], []] as const)
    ];
  }

  formatAssemblyAndGlueAsReact<T>(assembly: ConstantAssembly, options: {
    createElement: CreateElementType<T>;
    style?: 'label' | 'symbol' | undefined;
  }): [Node<T>, Node<T>] {
    let glue = null;
    let output: (Node<T> | string)[] = [];

    for (let [index, [unitId, power]] of assembly.entries()) {
      let unit = this.data.units[unitId];

      if (index > 0) {
        output.push((power < 0 ? '/' : '\xb7')); // &middot;
      }

      let plural = (index < 1) && (power > 0);
      let assemblyItem;

      switch (options.style ?? 'symbol') {
        case 'label':
          assemblyItem = plural ? unit.label[1] : unit.label[0];
          break;
        case 'symbol':
          assemblyItem = plural ? unit.symbol[1] : unit.symbol[0];
          break;
      }

      glue ??= assemblyItem.startsWith('\xb0') ? '' : '\xa0'; // &degree; &nbsp;
      output.push(assemblyItem);

      if ((power !== 1) && ((index < 1) || (power !== -1))) {
        output.push(options.createElement('sup', { key: output.length },
          (index > 0 ? Math.abs(power) : power).toString()
        ));
      }
    }

    return [glue ?? '', output];
  }

  formatAssemblyAsReact<T>(assembly: ConstantAssembly, options: {
    createElement: CreateElementType<T>;
    style?: 'label' | 'symbol' | undefined;
  }): Node<T> {
    return this.formatAssemblyAndGlueAsReact(assembly, options)[1];
  }

  formatAssemblyAsText(assembly: ConstantAssembly, options?: {
    style?: 'label' | 'symbol';
  }) {
    let output = '';

    for (let [index, [unitId, power]] of assembly.entries()) {
      let unit = this.data.units[unitId];

      if (index > 0) {
        output += (power < 0 ? '/' : '\xb7'); // &middot;
      }

      let plural = (index < 1) && (power > 0);

      switch (options?.style ?? 'symbol') {
        case 'label':
          output += (plural ? unit.label[1] : unit.label[0]);
          break;
        case 'symbol':
          output += (plural ? unit.symbol[1] : unit.symbol[0]);
          break;
      }

      if ((power !== 1) && ((index < 1) || (power !== -1))) {
        output += formatSuperscript(index > 0 ? Math.abs(power) : power);
      }
    }

    return output;
  }

  formatMagnitude(value: number, resolution: number, option: ContextVariantOption, options?: { sign?: unknown; }) {
    let magnitude = (value - this.getOptionOffset(option)) / option.value;
    let decimalCount = Math.max(0, Math.ceil(-Math.log10(resolution / option.value)));

    return [
      ...((magnitude < 0)
        ? ['\u2212\u2009'] // &minus; &thinsp;
        : options?.sign
          ? ['+\u2009']
          : []),
      Math.abs(magnitude).toFixed(isFinite(decimalCount) ? decimalCount : 0)
    ].join('');
  }

  formatRangeAsReact<T>(min: number, max: number, resolution: number, context: Context | string, options: { createElement: CreateElementType<T>; }) {
    let variant = this.findVariant(this.getContext(context), { system: 'SI' });

    return this.formatRangeWithContextAsReact(
      min,
      max,
      resolution,
      this.findBestVariantOption(min, variant),
      this.findBestVariantOption(max, variant),
      options
    );
  }

  formatRangeWithContextAsReact<T>(min: number, max: number, resolution: number, minOption: ContextVariantOption, maxOption: ContextVariantOption, options: { createElement: CreateElementType<T>; }) {
    return [
      ...this.formatQuantityWithContextAsReact(this.applyResolutionToBound(min, resolution), resolution, minOption, { ...options, skipUnit: (maxOption === minOption) }),
      ' \u2014 ', // &mdash;
      ...this.formatQuantityWithContextAsReact(this.applyResolutionToBound(max, resolution), resolution, maxOption, options)
    ];
  }
}
