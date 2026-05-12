import type { ColumnType, DataframeArtifact } from "../artifacts/types";

export type PlotKind = "histogram" | "scatter" | "box" | "violin" | "heatmap" | "pca" | "line";

export type PlotParamField = {
  name: string;
  label: string;
  type: "column" | "columns" | "int" | "bool" | "enum";
  column_filter?: ColumnType[];
  required: boolean;
  default?: unknown;
  options?: string[];
  hint?: string;
};

export type PlotSchema = {
  kind: PlotKind;
  label: string;
  description: string;
  fields: PlotParamField[];
};

export const PLOT_SCHEMAS: Record<PlotKind, PlotSchema> = {
  histogram: {
    kind: "histogram",
    label: "Histogram",
    description: "Distribution of one numeric column.",
    fields: [
      { name: "x_col", label: "X column", type: "column", column_filter: ["numeric"], required: true },
      { name: "bins", label: "Bins", type: "int", required: false, default: 30 },
      { name: "log_scale", label: "Log y-axis", type: "bool", required: false, default: false },
      { name: "group_col", label: "Group by (optional)", type: "column", column_filter: ["categorical"], required: false },
    ],
  },
  scatter: {
    kind: "scatter",
    label: "Scatter",
    description: "Two numeric columns; optional color/size encodings.",
    fields: [
      { name: "x_col", label: "X column", type: "column", column_filter: ["numeric"], required: true },
      { name: "y_col", label: "Y column", type: "column", column_filter: ["numeric"], required: true },
      { name: "color_col", label: "Color by (optional)", type: "column", column_filter: ["categorical", "numeric"], required: false },
    ],
  },
  box: {
    kind: "box",
    label: "Box plot",
    description: "Numeric distribution per group.",
    fields: [
      { name: "value_col", label: "Value column", type: "column", column_filter: ["numeric"], required: true },
      { name: "group_col", label: "Group column", type: "column", column_filter: ["categorical"], required: false },
    ],
  },
  violin: {
    kind: "violin",
    label: "Violin",
    description: "Like box but shows the density.",
    fields: [
      { name: "value_col", label: "Value column", type: "column", column_filter: ["numeric"], required: true },
      { name: "group_col", label: "Group column", type: "column", column_filter: ["categorical"], required: false },
    ],
  },
  heatmap: {
    kind: "heatmap",
    label: "Correlation heatmap",
    description: "Pearson correlation matrix across numeric columns.",
    fields: [
      {
        name: "feature_cols",
        label: "Numeric columns",
        type: "columns",
        column_filter: ["numeric"],
        required: false,
        hint: "Leave empty to use all numeric columns.",
      },
    ],
  },
  pca: {
    kind: "pca",
    label: "PCA scatter",
    description: "First two principal components of the chosen numeric columns.",
    fields: [
      { name: "feature_cols", label: "Numeric columns (≥ 2)", type: "columns", column_filter: ["numeric"], required: true },
      { name: "color_col", label: "Color by (optional)", type: "column", column_filter: ["categorical"], required: false },
    ],
  },
  line: {
    kind: "line",
    label: "Line chart",
    description: "Y vs X (often used for time series).",
    fields: [
      { name: "x_col", label: "X column", type: "column", column_filter: ["numeric", "datetime"], required: true },
      { name: "y_col", label: "Y column", type: "column", column_filter: ["numeric"], required: true },
      { name: "group_col", label: "Group by (optional)", type: "column", column_filter: ["categorical"], required: false },
    ],
  },
};

export function getSchema(kind: PlotKind): PlotSchema {
  return PLOT_SCHEMAS[kind];
}

export type ValidationOutcome = { ok: true } | { ok: false; errors: string[] };

export function validateParams(
  kind: PlotKind,
  params: Record<string, unknown>,
  df: DataframeArtifact,
): ValidationOutcome {
  const schema = PLOT_SCHEMAS[kind];
  if (!schema) return { ok: false, errors: [`Unknown plot kind: ${kind}`] };
  const errs: string[] = [];
  const colByName = Object.fromEntries(df.columns.map((c) => [c.name, c]));

  for (const field of schema.fields) {
    const v = params[field.name];
    if (v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0)) {
      if (field.required) errs.push(`${field.name}: required`);
      continue;
    }
    if (field.type === "column") {
      if (typeof v !== "string") {
        errs.push(`${field.name}: expected column name string`);
        continue;
      }
      const col = colByName[v];
      if (!col) {
        errs.push(`${field.name}: unknown column "${v}"`);
        continue;
      }
      if (field.column_filter && !field.column_filter.includes(col.type)) {
        errs.push(
          `${field.name}: "${v}" is ${col.type}; expected one of [${field.column_filter.join(", ")}]`,
        );
      }
    } else if (field.type === "columns") {
      if (!Array.isArray(v)) {
        errs.push(`${field.name}: expected array of column names`);
        continue;
      }
      for (const name of v) {
        if (typeof name !== "string" || !colByName[name]) {
          errs.push(`${field.name}: unknown column "${name}"`);
        } else if (field.column_filter && !field.column_filter.includes(colByName[name].type)) {
          errs.push(
            `${field.name}: "${name}" is ${colByName[name].type}; expected one of [${field.column_filter.join(", ")}]`,
          );
        }
      }
    } else if (field.type === "int") {
      if (typeof v !== "number" || !Number.isFinite(v) || !Number.isInteger(v) || v <= 0) {
        errs.push(`${field.name}: must be a positive integer`);
      }
    } else if (field.type === "bool") {
      if (typeof v !== "boolean") errs.push(`${field.name}: must be boolean`);
    } else if (field.type === "enum") {
      if (typeof v !== "string" || !field.options?.includes(v)) {
        errs.push(`${field.name}: must be one of [${field.options?.join(", ")}]`);
      }
    }
  }

  return errs.length === 0 ? { ok: true } : { ok: false, errors: errs };
}

export function listKinds(): PlotKind[] {
  return Object.keys(PLOT_SCHEMAS) as PlotKind[];
}
