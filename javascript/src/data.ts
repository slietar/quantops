export type ContextName = string;
export type SystemName = string;
export type UnitId = string;

export interface Unit {
  label: [string, string];
  symbol: [string, string];
  value: number;
}

export interface Data {
  contexts: Record<ContextName, Context>;
  units: Record<UnitId, Unit>;
}

export interface Context {
  variants: ContextVariant[];
}

export type ConstantAssemblyPart = [UnitId, number];
export type ConstantAssembly = ConstantAssemblyPart[];

export interface ContextVariant {
  options: ContextVariantOption[];
  systems: SystemName[];
}

export interface ContextVariantOption {
  assembly: ConstantAssembly;
  value: number;
}
