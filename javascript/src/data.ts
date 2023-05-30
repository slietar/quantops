export type AssemblyName = string;
export type UnitId = string;

export interface Assembly {
  options: {
    components: {
      power: number;
      units: UnitId[];
    }[];
    variableIndex: number | null;
  }[];
}

export interface Unit {
  label: [string, string];
  symbol: [string, string];
  value: number;
}

export interface Data {
  assemblies: Record<AssemblyName, Assembly>;
  units: Record<UnitId, Unit>;
}
