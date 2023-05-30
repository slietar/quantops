import { FunctionComponent, ReactNode, createElement } from 'react';
import { inspect } from 'node:util';

import untypedRegistryData from './data.json';

const registryData = untypedRegistryData as Data;


type AssemblyName = string;
type UnitId = string;

interface Assembly {
  options: {
    components: {
      power: number;
      units: UnitId[];
    }[];
    variableIndex: number | null;
  }[];
}

interface Unit {
  label: [string, string];
  symbol: [string, string];
  value: number;
}

interface Data {
  assemblies: Record<AssemblyName, Assembly>;
  units: Record<UnitId, Unit>;
}


export function format<T>(value: number, assemblyName: AssemblyName, options: {
  mode: {
    type: 'react';
    createElement(tag: string, attributes: Record<string, any> | null | undefined, ...children: ReactNode[]): T;
  };
  resolution?: number;
  style?: 'label' | 'symbol';
}) {
  let assemblyOptions = findAssemblyOptions(assemblyName);

  let sortedOptions = assemblyOptions.sort((a, b) => {
    let aValue = a.value * value;
    let bValue = b.value * value;

    return Number(aValue < 1) - Number(bValue < 1) || (aValue - bValue);
  });

  let bestOption = sortedOptions[0];
  let resolution = options.resolution ?? (value / 100);
  let decimalCount = Math.max(0, Math.ceil(-Math.log10(resolution * bestOption.value)));

  let output: (T | string)[] = [
    (bestOption.value * value).toFixed(decimalCount),
    '&nbsp;'
  ];

  for (let [index, [unit, power]] of bestOption.components.entries()) {
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
      output.push(options.mode.createElement('sup', {},
        (index > 0 ? Math.abs(power) : power).toString()
      ));
    }
  }

  return output;
}

export function getOptionsForRange(min: number, max: number) {

}

export function findAssemblyOptions(assemblyName: AssemblyName) {
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
