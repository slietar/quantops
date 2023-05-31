import type { ReactNode } from 'react';

import untypedRegistryData from '../data/registry.json';
import type { AssemblyName, Data, Unit } from './data.js';


const registryData = untypedRegistryData as Data;


export interface CompositeUnitFormat {
  components: (readonly [Unit, number])[];
  value: number;
}


export type CreateElementType<T> = (tag: string, attributes: Record<string, any> | null | undefined, ...children: ReactNode[]) => T;


export function findBestCompositeUnitFormat(value: number, formats: CompositeUnitFormat[]) {
  return formats.slice().sort((a, b) => {
    let aValue = a.value * value;
    let bValue = b.value * value;

    let bool = (v: boolean) => v ? 1 : -1;
    return (bool(aValue < 1) - bool(bValue < 1)) || (aValue - bValue) * bool(aValue > 1);
  })[0];
}

export function filterRangeCompositeUnitFormats(min: number, max: number, formats: CompositeUnitFormat[]) {
  let minFormat = findBestCompositeUnitFormat(min, formats);
  let maxFormat = findBestCompositeUnitFormat(max, formats);

  let sortedFormats = formats
    .slice()
    .sort((a, b) => (b.value - a.value));

  return sortedFormats.slice(
    sortedFormats.indexOf(minFormat),
    sortedFormats.indexOf(maxFormat) + 1
  );
}

export function formatUnitAsReact<T>(assembly: CompositeUnitFormat, options: {
  createElement: CreateElementType<T>;
  style?: 'label' | 'symbol';
}) {
  let output: (T | string)[] = [];

  for (let [index, [unit, power]] of assembly.components.entries()) {
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

export function formatQuantityAsReact<T>(value: number, resolution: number, assembly: CompositeUnitFormat, options: {
  createElement: CreateElementType<T>;
  skipUnit?: boolean;
}) {
  return [
    ...formatMagnitudeAsReact(value * assembly.value, resolution * assembly.value),
    ...(!options.skipUnit && (assembly.components.length > 0)
      ? [
        '&nbsp;',
        ...formatUnitAsReact(assembly, { createElement: options.createElement })
      ]
      : [])
  ];
}

export function formatMagnitudeAsReact(value: number, resolution: number) {
  let decimalCount = Math.max(0, Math.ceil(-Math.log10(resolution)));

  return [
    ...(value < 0 ? ['&ndash;'] : []),
    Math.abs(value).toFixed(decimalCount)
  ];
}

export function formatRangeAsReact<T>(min: number, max: number, resolution: number, minAssembly: CompositeUnitFormat, maxAssembly: CompositeUnitFormat, options: { createElement: CreateElementType<T> }) {
  return [
    ...formatQuantityAsReact(min, resolution, minAssembly, { ...options, skipUnit: (maxAssembly === minAssembly) }),
    ' &mdash; ',
    ...formatQuantityAsReact(max, resolution, maxAssembly, options)
  ];
}

export function findCompositeUnitFormats(assemblyName: AssemblyName): CompositeUnitFormat[] {
  let assembly = registryData.assemblies[assemblyName];
  let unitMatches = (unit: Unit) => true;

  let options = assembly.options.flatMap((option) => {
    let optionValue = 1;

    let optionComponents = option.components
      .filter((_, componentIndex) => (componentIndex !== option.variableIndex))
      .map(({ power, units: unitIds }) => {
        let units = unitIds.map((unitId) => registryData.units[unitId]);
        let matchingUnit = units.find((unit) => unitMatches(unit));

        if (!matchingUnit) {
          throw new Error('No matching unit');
        }

        optionValue /= matchingUnit.value ** power;
        return [matchingUnit, power] as const;
      });


    if (option.variableIndex !== null) {
      let variableIndex = option.variableIndex;

      let variableComponent = option.components[option.variableIndex];
      let variableUnits = variableComponent.units
        .map((unitId) => registryData.units[unitId])
        .filter((unit) => unitMatches(unit));

      return variableUnits.map((variableUnit) => ({
        components: [
          ...optionComponents.slice(0, variableIndex),
          [variableUnit, variableComponent.power] as const,
          ...optionComponents.slice(variableIndex)
        ],
        value: optionValue / (variableUnit.value ** variableComponent.power),
      }));
    } else {
      return [{
        components: optionComponents,
        value: optionValue
      }];
    }
  });

  return options;
}


function createSomeElement(tag: string, attributes: Record<string, any> | null | undefined, ...children: ReactNode[]): any {
  return {
    tag,
    attributes,
    children
  };
}


// let x = format(10 * 2 / 3, 'velocity', {
//   mode: {
//     type: 'react',
//     createElement: (createAElement as typeof createElement)
//   },
//   resolution: 0.3
// });


// console.log(x);
// console.log(inspect(x, { colors: true, depth: null }));


// let formats = findCompositeUnitFormats('velocity');
// let bestFormat = findBestCompositeUnitFormat(2e-3, formats);

// // console.log(bestFormat.map((x) => x.value * 2e-3));
// console.log(filterRangeCompositeUnitFormats(1e-3, 1e3, formats).map((x) => `${x.components[0][0].symbol[0]}/${x.components[1][0].symbol[0]} (${x.value})`));

// console.log(
//   formatRangeAsReact(3, 3200, 0.1, findBestCompositeUnitFormat(3, formats), findBestCompositeUnitFormat(3200, formats), { createElement: createSomeElement })
// )
