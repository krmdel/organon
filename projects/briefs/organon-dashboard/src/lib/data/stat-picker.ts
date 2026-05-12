import type {
  AssumptionVerdict,
  CategoricalColumnStats,
  ColumnType,
  DataframeArtifact,
  DataframeColumn,
  NumericColumnStats,
} from "../artifacts/types";

export type ComparisonMode =
  | "group"
  | "correlation"
  | "regression"
  | "contingency"
  | "power";

export type GroupAnswers = {
  mode: "group";
  value_col: string;
  group_col: string;
  paired: boolean;
};

export type CorrelationAnswers = {
  mode: "correlation";
  x_col: string;
  y_col: string;
};

export type RegressionAnswers = {
  mode: "regression";
  target_col: string;
  predictor_cols: string[];
};

export type ContingencyAnswers = {
  mode: "contingency";
  row_col: string;
  col_col: string;
};

export type PowerAnswers = {
  mode: "power";
  test_kind: "t-test" | "anova" | "correlation" | "chi2";
  effect_size: number;
  alpha: number;
  power_target?: number;
  n?: number;
};

export type WizardAnswers =
  | GroupAnswers
  | CorrelationAnswers
  | RegressionAnswers
  | ContingencyAnswers
  | PowerAnswers;

export type AssumptionFlag = {
  name: string;
  verdict: AssumptionVerdict | "unknown";
  note?: string;
};

export type Recommendation = {
  test_name: string;
  test_label: string;
  reasoning: string;
  assumption_flags: AssumptionFlag[];
  params: Record<string, unknown>;
  rank: number;
};

export type StatPickerError = { error: string };
export type StatPickerResult = { recommendations: Recommendation[] };

function getColumn(df: DataframeArtifact, name: string): DataframeColumn | null {
  return df.columns.find((c) => c.name === name) ?? null;
}

function rejectIfMissing(
  df: DataframeArtifact,
  cols: string[],
): StatPickerError | null {
  const missing = cols.filter((c) => !getColumn(df, c));
  if (missing.length > 0) {
    return { error: `Unknown columns: ${missing.join(", ")}` };
  }
  return null;
}

function expectType(
  df: DataframeArtifact,
  col: string,
  expected: ColumnType[],
): StatPickerError | null {
  const c = getColumn(df, col);
  if (!c) return { error: `Unknown column: ${col}` };
  if (!expected.includes(c.type)) {
    return {
      error: `Column "${col}" must be one of [${expected.join(", ")}]; got "${c.type}". Override the type chip in the preview to fix.`,
    };
  }
  return null;
}

function nonNullCount(col: DataframeColumn): number {
  if (col.type === "numeric") return (col.stats as NumericColumnStats).count;
  if (col.type === "categorical")
    return (col.stats as CategoricalColumnStats).top.reduce((a, [, n]) => a + n, 0);
  if (col.type === "datetime")
    return (col.stats as { count: number }).count;
  return (col.stats as { count: number }).count;
}

function groupCardinality(col: DataframeColumn): number | null {
  if (col.type !== "categorical") return null;
  return (col.stats as CategoricalColumnStats).unique_count;
}

function smallestGroupN(col: DataframeColumn): number | null {
  if (col.type !== "categorical") return null;
  const top = (col.stats as CategoricalColumnStats).top;
  if (top.length === 0) return null;
  return Math.min(...top.map(([, n]) => n));
}

function recommendForGroup(
  df: DataframeArtifact,
  ans: GroupAnswers,
): StatPickerError | StatPickerResult {
  const valueErr = expectType(df, ans.value_col, ["numeric"]);
  if (valueErr) return valueErr;
  const groupErr = expectType(df, ans.group_col, ["categorical"]);
  if (groupErr) return groupErr;

  const group = getColumn(df, ans.group_col)!;
  const value = getColumn(df, ans.value_col)!;
  const k = groupCardinality(group);
  const small = smallestGroupN(group);
  const nValue = nonNullCount(value);

  if (k === null) {
    return { error: `Could not infer group cardinality for "${ans.group_col}".` };
  }
  if (k < 2) {
    return {
      error: `Group column "${ans.group_col}" has only ${k} category. Need ≥ 2 groups.`,
    };
  }

  const sampleFlag = (n: number | null): AssumptionFlag => ({
    name: "min_group_n",
    verdict: n === null ? "unknown" : n >= 30 ? "pass" : n >= 10 ? "warn" : "fail",
    note: n === null ? undefined : `smallest group n = ${n}`,
  });

  const normalityFlag: AssumptionFlag = {
    name: "normality_shapiro",
    verdict: "unknown",
    note: "Verified at run time via Shapiro–Wilk on each group.",
  };
  const equalVarianceFlag: AssumptionFlag = {
    name: "equal_variance_levene",
    verdict: "unknown",
    note: "Verified at run time via Levene's test; Welch correction applied if it fails.",
  };

  const recs: Recommendation[] = [];

  if (k === 2 && ans.paired) {
    recs.push({
      test_name: "ttest_rel",
      test_label: "Paired t-test",
      reasoning: `2 paired groups, numeric outcome. Default parametric choice when within-pair differences are roughly normal (n=${nValue}).`,
      assumption_flags: [normalityFlag, sampleFlag(small)],
      params: { value_col: ans.value_col, group_col: ans.group_col, paired: true, alpha: 0.05 },
      rank: 1,
    });
    recs.push({
      test_name: "wilcoxon",
      test_label: "Wilcoxon signed-rank",
      reasoning: "Non-parametric fallback when paired differences are not normal or have outliers.",
      assumption_flags: [sampleFlag(small)],
      params: { value_col: ans.value_col, group_col: ans.group_col, paired: true, alpha: 0.05 },
      rank: 2,
    });
  } else if (k === 2 && !ans.paired) {
    recs.push({
      test_name: "ttest_ind",
      test_label: "Two-sample t-test (Welch)",
      reasoning: `2 independent groups, numeric outcome. Welch's correction handles unequal variance automatically; robust default for moderate samples (smallest group n=${small ?? "?"}).`,
      assumption_flags: [normalityFlag, equalVarianceFlag, sampleFlag(small)],
      params: {
        value_col: ans.value_col,
        group_col: ans.group_col,
        paired: false,
        alpha: 0.05,
        equal_var: false,
      },
      rank: 1,
    });
    recs.push({
      test_name: "mannwhitneyu",
      test_label: "Mann–Whitney U",
      reasoning: "Non-parametric fallback when normality fails or n is small (< 30 per group).",
      assumption_flags: [sampleFlag(small)],
      params: { value_col: ans.value_col, group_col: ans.group_col, alpha: 0.05 },
      rank: 2,
    });
  } else if (k > 2 && !ans.paired) {
    recs.push({
      test_name: "anova_oneway",
      test_label: "One-way ANOVA",
      reasoning: `${k} independent groups, numeric outcome. Parametric default; follow up with Tukey HSD if the omnibus is significant.`,
      assumption_flags: [normalityFlag, equalVarianceFlag, sampleFlag(small)],
      params: { value_col: ans.value_col, group_col: ans.group_col, alpha: 0.05 },
      rank: 1,
    });
    recs.push({
      test_name: "kruskal_wallis",
      test_label: "Kruskal–Wallis",
      reasoning: "Non-parametric omnibus when ANOVA assumptions fail or groups are small.",
      assumption_flags: [sampleFlag(small)],
      params: { value_col: ans.value_col, group_col: ans.group_col, alpha: 0.05 },
      rank: 2,
    });
  } else {
    recs.push({
      test_name: "friedman",
      test_label: "Friedman test",
      reasoning: `${k} repeated-measure groups, numeric outcome. Non-parametric default for paired designs with > 2 conditions.`,
      assumption_flags: [sampleFlag(small)],
      params: { value_col: ans.value_col, group_col: ans.group_col, paired: true, alpha: 0.05 },
      rank: 1,
    });
  }

  return { recommendations: recs };
}

function recommendForCorrelation(
  df: DataframeArtifact,
  ans: CorrelationAnswers,
): StatPickerError | StatPickerResult {
  const xErr = expectType(df, ans.x_col, ["numeric"]);
  if (xErr) return xErr;
  const yErr = expectType(df, ans.y_col, ["numeric"]);
  if (yErr) return yErr;

  const x = getColumn(df, ans.x_col)!;
  const sampleFlag: AssumptionFlag = {
    name: "n_check",
    verdict: nonNullCount(x) >= 30 ? "pass" : "warn",
    note: `n = ${nonNullCount(x)}`,
  };

  return {
    recommendations: [
      {
        test_name: "pearson",
        test_label: "Pearson correlation",
        reasoning: "Default linear-association test for two numeric variables.",
        assumption_flags: [
          { name: "linearity", verdict: "unknown", note: "Inspect a scatter plot first." },
          { name: "normality", verdict: "unknown" },
          sampleFlag,
        ],
        params: { x_col: ans.x_col, y_col: ans.y_col, alpha: 0.05 },
        rank: 1,
      },
      {
        test_name: "spearman",
        test_label: "Spearman rank correlation",
        reasoning: "Non-parametric fallback for monotonic but non-linear relationships, or when outliers dominate.",
        assumption_flags: [sampleFlag],
        params: { x_col: ans.x_col, y_col: ans.y_col, alpha: 0.05 },
        rank: 2,
      },
    ],
  };
}

function recommendForRegression(
  df: DataframeArtifact,
  ans: RegressionAnswers,
): StatPickerError | StatPickerResult {
  const targetErr = expectType(df, ans.target_col, ["numeric", "categorical"]);
  if (targetErr) return targetErr;
  const predictorErr = rejectIfMissing(df, ans.predictor_cols);
  if (predictorErr) return predictorErr;
  if (ans.predictor_cols.length === 0) {
    return { error: "At least one predictor column required." };
  }

  const target = getColumn(df, ans.target_col)!;
  const isBinary =
    target.type === "categorical" &&
    (target.stats as CategoricalColumnStats).unique_count === 2;

  if (isBinary) {
    return {
      recommendations: [
        {
          test_name: "logistic_regression",
          test_label: "Logistic regression",
          reasoning: `Binary target ("${ans.target_col}") with ${ans.predictor_cols.length} predictor(s). Reports odds ratios + CIs.`,
          assumption_flags: [
            {
              name: "linearity_logit",
              verdict: "unknown",
              note: "Linearity assumption is on the log-odds scale.",
            },
            {
              name: "no_perfect_separation",
              verdict: "unknown",
            },
          ],
          params: {
            target_col: ans.target_col,
            predictor_cols: ans.predictor_cols,
            alpha: 0.05,
          },
          rank: 1,
        },
      ],
    };
  }

  return {
    recommendations: [
      {
        test_name: "linear_regression",
        test_label: "Linear regression",
        reasoning: `Numeric target ("${ans.target_col}") with ${ans.predictor_cols.length} predictor(s). Reports coefficients + R² + residual diagnostics.`,
        assumption_flags: [
          { name: "linearity", verdict: "unknown" },
          { name: "homoscedasticity", verdict: "unknown" },
          { name: "residual_normality", verdict: "unknown" },
          { name: "no_multicollinearity", verdict: "unknown" },
        ],
        params: {
          target_col: ans.target_col,
          predictor_cols: ans.predictor_cols,
          alpha: 0.05,
        },
        rank: 1,
      },
    ],
  };
}

function recommendForContingency(
  df: DataframeArtifact,
  ans: ContingencyAnswers,
): StatPickerError | StatPickerResult {
  const rowErr = expectType(df, ans.row_col, ["categorical"]);
  if (rowErr) return rowErr;
  const colErr = expectType(df, ans.col_col, ["categorical"]);
  if (colErr) return colErr;

  const row = getColumn(df, ans.row_col)!;
  const col = getColumn(df, ans.col_col)!;
  const rowK = groupCardinality(row) ?? 0;
  const colK = groupCardinality(col) ?? 0;
  const is2x2 = rowK === 2 && colK === 2;

  const recs: Recommendation[] = [
    {
      test_name: "chi2_contingency",
      test_label: "Chi-squared test",
      reasoning: `${rowK}×${colK} contingency table. Default omnibus for two categorical variables; reports Cramér's V.`,
      assumption_flags: [
        {
          name: "expected_count",
          verdict: "unknown",
          note: "All expected counts should be ≥ 5; verify at run time.",
        },
      ],
      params: { row_col: ans.row_col, col_col: ans.col_col, alpha: 0.05 },
      rank: 1,
    },
  ];
  if (is2x2) {
    recs.push({
      test_name: "fisher_exact",
      test_label: "Fisher's exact test",
      reasoning: "Exact alternative for 2×2 tables, particularly when expected counts are small.",
      assumption_flags: [],
      params: { row_col: ans.row_col, col_col: ans.col_col, alpha: 0.05 },
      rank: 2,
    });
  }
  return { recommendations: recs };
}

function recommendForPower(ans: PowerAnswers): StatPickerError | StatPickerResult {
  if (ans.power_target === undefined && ans.n === undefined) {
    return { error: "Specify either a power target (0–1) or a sample size n." };
  }
  if (ans.alpha <= 0 || ans.alpha >= 1) {
    return { error: "alpha must be in (0, 1)." };
  }
  if (ans.effect_size <= 0) {
    return { error: "effect_size must be > 0." };
  }
  return {
    recommendations: [
      {
        test_name: `power_${ans.test_kind.replace("-", "_")}`,
        test_label: `Power analysis (${ans.test_kind})`,
        reasoning:
          ans.n !== undefined
            ? `Computes achieved power given n=${ans.n}, effect=${ans.effect_size}, α=${ans.alpha}.`
            : `Computes required n given target power=${ans.power_target}, effect=${ans.effect_size}, α=${ans.alpha}.`,
        assumption_flags: [],
        params: {
          test_kind: ans.test_kind,
          effect_size: ans.effect_size,
          alpha: ans.alpha,
          power_target: ans.power_target,
          n: ans.n,
        },
        rank: 1,
      },
    ],
  };
}

/**
 * Pure-TS recommendation entry point. Same answers + dataframe always yield
 * the same recommendations — the skill is invoked only to RUN the chosen test.
 */
export function recommendTests(
  df: DataframeArtifact,
  answers: WizardAnswers,
): StatPickerError | StatPickerResult {
  switch (answers.mode) {
    case "group":
      return recommendForGroup(df, answers);
    case "correlation":
      return recommendForCorrelation(df, answers);
    case "regression":
      return recommendForRegression(df, answers);
    case "contingency":
      return recommendForContingency(df, answers);
    case "power":
      return recommendForPower(answers);
  }
}
