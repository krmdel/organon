"""Core data analysis operations for the sci-data-analysis skill.

Provides data loading/profiling, statistical testing with assumption checking,
data cleaning, regression analysis, and structured report generation.
All operations log to the reproducibility ledger via repro_logger.

Per D-01: Load CSV/Excel/JSON and profile.
Per D-02: Statistical tests with assumption checking.
Per D-03: Data cleaning (missing values, outliers, normalization).
Per D-04/D-07: Structured markdown report generation.
Per D-08: Linear and logistic regression.
Per D-09: All operations logged to reproducibility ledger.
"""

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import expit

# Add project root to sys.path for repro import
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from repro.repro_logger import log_operation


# ---------------------------------------------------------------------------
# Data Loading & Profiling (DATA-01)
# ---------------------------------------------------------------------------

def load_and_profile(filepath: str) -> tuple:
    """Load a data file and return (dataframe, profile_text).

    Supports CSV, Excel (.xlsx/.xls), and JSON formats.
    Builds a profile with shape, column types, null counts, and summary stats.

    Args:
        filepath: Path to the data file.

    Returns:
        Tuple of (pandas DataFrame, profile markdown string).

    Raises:
        ValueError: If file format is not supported.
    """
    p = Path(filepath)
    ext = p.suffix.lower()

    if ext == ".csv":
        df = pd.read_csv(filepath)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)
    elif ext == ".json":
        df = pd.read_json(filepath)
    else:
        raise ValueError(f"Unsupported format: {ext}. Supported: .csv, .xlsx, .xls, .json")

    # Build profile
    rows, cols = df.shape
    profile = f"**Shape:** {rows} rows x {cols} columns\n\n"
    profile += "**Columns:**\n"
    for col in df.columns:
        dtype = df[col].dtype
        nulls = int(df[col].isnull().sum())
        profile += f"- `{col}` ({dtype}) — {nulls} missing\n"
    profile += f"\n**Summary Statistics:**\n```\n{df.describe(include='all').to_string()}\n```"

    log_operation(
        skill="sci-data-analysis",
        operation="load_data",
        params={"filepath": str(filepath), "format": ext, "shape": [rows, cols]},
        data_files=[str(filepath)],
    )

    return df, profile


# ---------------------------------------------------------------------------
# Statistical Testing (DATA-02)
# ---------------------------------------------------------------------------

def _shapiro_check(data: np.ndarray, alpha: float) -> dict:
    """Run Shapiro-Wilk normality test with sample size guards."""
    n = len(data)
    if n < 3:
        return {"statistic": None, "p_value": None, "passed": None, "note": "n < 3, cannot test"}
    if n > 5000:
        return {"statistic": None, "p_value": None, "passed": None, "note": "n > 5000, use visual inspection"}
    stat, p = stats.shapiro(data)
    return {"statistic": float(stat), "p_value": float(p), "passed": bool(p > alpha)}


def _cohens_d(group_a: np.ndarray, group_b: np.ndarray) -> float:
    """Compute Cohen's d effect size for two independent groups."""
    n_a, n_b = len(group_a), len(group_b)
    pooled_std = math.sqrt(
        ((n_a - 1) * np.std(group_a, ddof=1) ** 2
         + (n_b - 1) * np.std(group_b, ddof=1) ** 2)
        / (n_a + n_b - 2)
    )
    if pooled_std == 0:
        return 0.0
    return float((np.mean(group_a) - np.mean(group_b)) / pooled_std)


def _cramers_v(contingency_table: np.ndarray, chi2: float, n: int) -> float:
    """Compute Cramer's V from chi-square statistic."""
    min_dim = min(contingency_table.shape) - 1
    if min_dim == 0 or n == 0:
        return 0.0
    return float(math.sqrt(chi2 / (n * min_dim)))


def _effect_size_label(d: float) -> str:
    """Classify effect size magnitude."""
    d_abs = abs(d)
    if d_abs < 0.2:
        return "negligible"
    elif d_abs < 0.5:
        return "small"
    elif d_abs < 0.8:
        return "medium"
    else:
        return "large"


def run_statistical_test(
    df: pd.DataFrame,
    test_type: str,
    columns: dict,
    alpha: float = 0.05,
) -> dict:
    """Run a statistical test with assumption checking.

    Args:
        df: Input DataFrame.
        test_type: One of 'ttest_ind', 'ttest_paired', 'anova', 'chi_square', 'pearson', 'spearman'.
        columns: Dict with column references. Keys depend on test_type:
            - ttest_ind/ttest_paired: group_col, value_col
            - anova: group_col, value_col
            - chi_square: col_a, col_b
            - pearson/spearman: col_a, col_b
        alpha: Significance level (default 0.05).

    Returns:
        Dict with test_name, assumptions, statistic, p_value, effect_size,
        significant, and optionally alternative_suggested.
    """
    results: dict = {"test_type": test_type, "alpha": alpha}

    if test_type == "ttest_ind":
        group_col = columns["group_col"]
        value_col = columns["value_col"]
        groups = df.groupby(group_col)[value_col].apply(lambda x: x.dropna().values)
        group_names = list(groups.index)
        if len(group_names) < 2:
            raise ValueError(f"Need at least 2 groups in '{group_col}', found {len(group_names)}")
        group_a = groups.iloc[0]
        group_b = groups.iloc[1]

        norm_a = _shapiro_check(group_a, alpha)
        norm_b = _shapiro_check(group_b, alpha)
        lev_stat, lev_p = stats.levene(group_a, group_b)
        homogeneity = {"statistic": float(lev_stat), "p_value": float(lev_p), "passed": bool(lev_p > alpha)}

        equal_var = homogeneity["passed"]
        t_stat, p_val = stats.ttest_ind(group_a, group_b, equal_var=equal_var)
        d = _cohens_d(group_a, group_b)

        # 95% CI for mean difference
        mean_diff = float(np.mean(group_a) - np.mean(group_b))
        se_diff = math.sqrt(np.var(group_a, ddof=1) / len(group_a)
                            + np.var(group_b, ddof=1) / len(group_b))
        df_val = len(group_a) + len(group_b) - 2
        t_crit = stats.t.ppf(0.975, df_val)
        ci_95 = (mean_diff - t_crit * se_diff, mean_diff + t_crit * se_diff)

        test_name = "Welch's t-test" if not equal_var else "Student's t-test"
        assumptions_pass = all([
            norm_a.get("passed") is not False,
            norm_b.get("passed") is not False,
            homogeneity["passed"],
        ])

        results.update({
            "test_name": test_name,
            "assumptions": {
                "normality_a": norm_a,
                "normality_b": norm_b,
                "homogeneity": homogeneity,
            },
            "statistic": float(t_stat),
            "p_value": float(p_val),
            "effect_size": d,
            "effect_size_label": _effect_size_label(d),
            "ci_95": (float(ci_95[0]), float(ci_95[1])),
            "significant": bool(p_val < alpha),
        })
        if not assumptions_pass:
            results["alternative_suggested"] = "Mann-Whitney U test (non-parametric alternative)"

    elif test_type == "ttest_paired":
        col_a = columns["col_a"]
        col_b = columns["col_b"]
        data_a = df[col_a].dropna().values
        data_b = df[col_b].dropna().values
        min_len = min(len(data_a), len(data_b))
        data_a, data_b = data_a[:min_len], data_b[:min_len]

        norm_diff = _shapiro_check(data_a - data_b, alpha)
        t_stat, p_val = stats.ttest_rel(data_a, data_b)

        results.update({
            "test_name": "Paired t-test",
            "assumptions": {"normality_differences": norm_diff},
            "statistic": float(t_stat),
            "p_value": float(p_val),
            "significant": bool(p_val < alpha),
        })

    elif test_type == "anova":
        group_col = columns["group_col"]
        value_col = columns["value_col"]
        groups_series = df.groupby(group_col)[value_col].apply(lambda x: x.dropna().values)
        group_list = [g for g in groups_series]

        # Assumption checks per group
        normality = {}
        for name, data in groups_series.items():
            normality[str(name)] = _shapiro_check(data, alpha)

        all_vals = [v for g in group_list for v in g]
        lev_stat, lev_p = stats.levene(*group_list)
        homogeneity = {"statistic": float(lev_stat), "p_value": float(lev_p), "passed": bool(lev_p > alpha)}

        f_stat, p_val = stats.f_oneway(*group_list)

        # Eta-squared
        grand_mean = np.mean(all_vals)
        ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in group_list)
        ss_total = sum((v - grand_mean) ** 2 for v in all_vals)
        eta_squared = float(ss_between / ss_total) if ss_total > 0 else 0.0

        assumptions_pass = all(
            v.get("passed") is not False for v in normality.values()
        ) and homogeneity["passed"]

        results.update({
            "test_name": "One-way ANOVA",
            "assumptions": {"normality": normality, "homogeneity": homogeneity},
            "statistic": float(f_stat),
            "p_value": float(p_val),
            "effect_size": eta_squared,
            "effect_size_label": "eta-squared",
            "significant": bool(p_val < alpha),
        })
        if not assumptions_pass:
            results["alternative_suggested"] = "Kruskal-Wallis H test (non-parametric alternative)"
        if p_val < alpha:
            results["post_hoc_guidance"] = "Run Tukey HSD or pairwise t-tests with Bonferroni correction"

    elif test_type == "chi_square":
        col_a = columns["col_a"]
        col_b = columns["col_b"]
        contingency = pd.crosstab(df[col_a], df[col_b])
        chi2, p_val, dof, expected = stats.chi2_contingency(contingency)
        n = contingency.values.sum()
        v = _cramers_v(contingency.values, chi2, n)

        results.update({
            "test_name": "Chi-square test of independence",
            "assumptions": {
                "min_expected_frequency": float(expected.min()),
                "expected_freq_ok": bool(expected.min() >= 5),
            },
            "statistic": float(chi2),
            "p_value": float(p_val),
            "dof": int(dof),
            "cramers_v": v,
            "significant": bool(p_val < alpha),
        })

    elif test_type == "pearson":
        col_a_name = columns["col_a"]
        col_b_name = columns["col_b"]
        clean = df[[col_a_name, col_b_name]].dropna()
        r, p_val = stats.pearsonr(clean[col_a_name], clean[col_b_name])

        # CI via Fisher z-transform
        n = len(clean)
        z = np.arctanh(r)
        se = 1.0 / math.sqrt(n - 3) if n > 3 else float("inf")
        z_crit = stats.norm.ppf(0.975)
        ci_low = math.tanh(z - z_crit * se)
        ci_high = math.tanh(z + z_crit * se)

        results.update({
            "test_name": "Pearson correlation",
            "statistic": float(r),
            "p_value": float(p_val),
            "ci_95": (float(ci_low), float(ci_high)),
            "significant": bool(p_val < alpha),
        })

    elif test_type == "spearman":
        col_a_name = columns["col_a"]
        col_b_name = columns["col_b"]
        clean = df[[col_a_name, col_b_name]].dropna()
        rho, p_val = stats.spearmanr(clean[col_a_name], clean[col_b_name])

        results.update({
            "test_name": "Spearman rank correlation",
            "statistic": float(rho),
            "p_value": float(p_val),
            "significant": bool(p_val < alpha),
        })

    else:
        raise ValueError(f"Unknown test_type: {test_type}. Supported: ttest_ind, ttest_paired, anova, chi_square, pearson, spearman")

    log_operation(
        skill="sci-data-analysis",
        operation="statistical_test",
        params={"test_type": test_type, "columns": columns, "alpha": alpha},
    )

    return results


# ---------------------------------------------------------------------------
# Regression (DATA-02, D-08)
# ---------------------------------------------------------------------------

def run_regression(
    df: pd.DataFrame,
    x_cols: list,
    y_col: str,
    reg_type: str = "linear",
) -> dict:
    """Run regression analysis.

    Args:
        df: Input DataFrame.
        x_cols: List of predictor column names.
        y_col: Response column name.
        reg_type: 'linear' for OLS or 'logistic' for logistic regression.

    Returns:
        Dict with regression results.
    """
    clean = df[x_cols + [y_col]].dropna()

    if reg_type == "linear":
        if len(x_cols) == 1:
            x = clean[x_cols[0]].values.astype(float)
            y = clean[y_col].values.astype(float)
            result = stats.linregress(x, y)

            y_pred = result.slope * x + result.intercept
            residuals = y - y_pred
            n = len(x)
            r_squared = result.rvalue ** 2
            rse = float(np.sqrt(np.sum(residuals ** 2) / (n - 2))) if n > 2 else float("nan")

            t_crit = stats.t.ppf(0.975, df=n - 2) if n > 2 else float("nan")
            slope_ci = (
                float(result.slope - t_crit * result.stderr),
                float(result.slope + t_crit * result.stderr),
            )

            reg_results = {
                "reg_type": "linear",
                "slope": float(result.slope),
                "intercept": float(result.intercept),
                "r_squared": float(r_squared),
                "p_value": float(result.pvalue),
                "std_error": float(result.stderr),
                "slope_ci_95": slope_ci,
                "residual_std_error": rse,
                "residuals": residuals.tolist(),
                "predictions": y_pred.tolist(),
            }
        else:
            # Multiple linear regression via numpy
            X = clean[x_cols].values.astype(float)
            y = clean[y_col].values.astype(float)
            X_aug = np.column_stack([np.ones(len(X)), X])
            coeffs, residuals_sum, rank, sv = np.linalg.lstsq(X_aug, y, rcond=None)

            y_pred = X_aug @ coeffs
            residuals = y - y_pred
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

            reg_results = {
                "reg_type": "linear_multiple",
                "intercept": float(coeffs[0]),
                "coefficients": {col: float(c) for col, c in zip(x_cols, coeffs[1:])},
                "r_squared": float(r_squared),
                "residuals": residuals.tolist(),
                "predictions": y_pred.tolist(),
            }

    elif reg_type == "logistic":
        X = clean[x_cols].values.astype(float)
        y = clean[y_col].values.astype(float)

        # Standardize X for numerical stability
        x_mean = X.mean(axis=0)
        x_std = X.std(axis=0)
        x_std[x_std == 0] = 1.0
        X_s = (X - x_mean) / x_std
        X_aug = np.column_stack([np.ones(len(X_s)), X_s])

        def neg_log_likelihood(beta):
            z = X_aug @ beta
            # Clip to avoid overflow
            z = np.clip(z, -500, 500)
            ll = np.sum(y * z - np.log(1 + np.exp(z)))
            return -ll

        def grad(beta):
            z = X_aug @ beta
            p = expit(z)
            return -X_aug.T @ (y - p)

        n_params = X_aug.shape[1]
        beta0 = np.zeros(n_params)

        from scipy.optimize import minimize as sp_minimize
        opt = sp_minimize(neg_log_likelihood, beta0, jac=grad, method="BFGS")
        beta = opt.x

        # Transform coefficients back to original scale
        intercept = beta[0] - np.sum(beta[1:] * x_mean / x_std)
        coefs_orig = beta[1:] / x_std

        # Standard errors from inverse Hessian
        try:
            hess_inv = opt.hess_inv
            if hasattr(hess_inv, "todense"):
                hess_inv = np.array(hess_inv.todense())
            se = np.sqrt(np.diag(hess_inv))
            z_vals = beta / se
            p_vals = 2 * (1 - stats.norm.cdf(np.abs(z_vals)))
        except Exception:
            se = np.full(n_params, float("nan"))
            p_vals = np.full(n_params, float("nan"))

        odds_ratios = np.exp(coefs_orig)

        reg_results = {
            "reg_type": "logistic",
            "intercept": float(intercept),
            "coefficients": [float(c) for c in coefs_orig],
            "odds_ratios": [float(o) for o in odds_ratios],
            "p_values": [float(p) for p in p_vals[1:]],
            "log_likelihood": float(-opt.fun),
            "converged": bool(opt.success),
        }

    else:
        raise ValueError(f"Unknown reg_type: {reg_type}. Supported: linear, logistic")

    log_operation(
        skill="sci-data-analysis",
        operation="regression",
        params={"x_cols": x_cols, "y_col": y_col, "reg_type": reg_type},
    )

    return reg_results


# ---------------------------------------------------------------------------
# Data Cleaning (DATA-03)
# ---------------------------------------------------------------------------

def clean_data(
    df: pd.DataFrame,
    operations: list,
) -> tuple:
    """Apply a sequence of cleaning operations to a DataFrame.

    Args:
        df: Input DataFrame.
        operations: List of dicts, each with 'type' and operation-specific params.
            Supported types: drop_missing, fill_missing, interpolate_missing,
            remove_outliers, normalize.

    Returns:
        Tuple of (cleaned DataFrame, comparison markdown string).
    """
    result = df.copy()
    comparison_parts = []
    rows_before = len(result)

    for op in operations:
        op_type = op["type"]
        cols = op.get("columns", [])

        if op_type == "drop_missing":
            before_nulls = {c: int(result[c].isnull().sum()) for c in cols}
            result = result.dropna(subset=cols)
            after_nulls = {c: int(result[c].isnull().sum()) for c in cols}
            comparison_parts.append(
                f"**drop_missing** on {cols}: rows {rows_before} -> {len(result)}, "
                + ", ".join(f"`{c}` nulls {before_nulls[c]} -> {after_nulls[c]}" for c in cols)
            )

        elif op_type == "fill_missing":
            method = op.get("method", "mean")
            fill_value = op.get("value", None)
            before_nulls = {c: int(result[c].isnull().sum()) for c in cols}
            for c in cols:
                if method == "mean":
                    result[c] = result[c].fillna(result[c].mean())
                elif method == "median":
                    result[c] = result[c].fillna(result[c].median())
                elif method == "mode":
                    mode_val = result[c].mode()
                    if len(mode_val) > 0:
                        result[c] = result[c].fillna(mode_val.iloc[0])
                elif method == "value":
                    result[c] = result[c].fillna(fill_value)
            after_nulls = {c: int(result[c].isnull().sum()) for c in cols}
            comparison_parts.append(
                f"**fill_missing** ({method}) on {cols}: "
                + ", ".join(f"`{c}` nulls {before_nulls[c]} -> {after_nulls[c]}" for c in cols)
            )

        elif op_type == "interpolate_missing":
            method = op.get("method", "linear")
            before_nulls = {c: int(result[c].isnull().sum()) for c in cols}
            for c in cols:
                result[c] = result[c].interpolate(method=method)
            after_nulls = {c: int(result[c].isnull().sum()) for c in cols}
            comparison_parts.append(
                f"**interpolate_missing** ({method}) on {cols}: "
                + ", ".join(f"`{c}` nulls {before_nulls[c]} -> {after_nulls[c]}" for c in cols)
            )

        elif op_type == "remove_outliers":
            method = op.get("method", "iqr")
            factor = op.get("factor", 1.5)
            rows_before_op = len(result)
            for c in cols:
                q1 = result[c].quantile(0.25)
                q3 = result[c].quantile(0.75)
                iqr = q3 - q1
                lower = q1 - factor * iqr
                upper = q3 + factor * iqr
                result = result[(result[c] >= lower) & (result[c] <= upper)]
            comparison_parts.append(
                f"**remove_outliers** (IQR x{factor}) on {cols}: "
                f"rows before {rows_before_op}, rows after {len(result)}"
            )

        elif op_type == "normalize":
            method = op.get("method", "zscore")
            for c in cols:
                before_range = f"{result[c].min():.4f}-{result[c].max():.4f}"
                if method == "zscore":
                    result[c] = stats.zscore(result[c], nan_policy="omit")
                elif method == "minmax":
                    col_min = result[c].min()
                    col_max = result[c].max()
                    denom = col_max - col_min
                    if denom == 0:
                        result[c] = 0.0
                    else:
                        result[c] = (result[c] - col_min) / denom
                after_range = f"{result[c].min():.4f}-{result[c].max():.4f}"
                comparison_parts.append(
                    f"**normalize** ({method}) `{c}`: range {before_range} -> {after_range}"
                )

        else:
            raise ValueError(f"Unknown cleaning operation: {op_type}")

    rows_after = len(result)
    header = f"**Cleaning Summary:** rows before {rows_before}, rows after {rows_after}\n\n"
    comparison_text = header + "\n".join(f"- {p}" for p in comparison_parts)

    log_operation(
        skill="sci-data-analysis",
        operation="clean_data",
        params={"operations": operations, "rows_before": rows_before, "rows_after": rows_after},
    )

    return result, comparison_text


# ---------------------------------------------------------------------------
# Report Generation (DATA-04, D-07)
# ---------------------------------------------------------------------------

def generate_report(test_results: dict, test_type: str) -> str:
    """Generate a structured markdown report from statistical test results.

    Args:
        test_results: Dict returned by run_statistical_test.
        test_type: The type of test that was run.

    Returns:
        Markdown string with Test Selected, Assumptions Check, Results,
        Interpretation, and Recommendation sections.
    """
    lines = []

    # --- Test Selected ---
    test_name = test_results.get("test_name", test_type)
    lines.append(f"## Test Selected\n")
    lines.append(f"**{test_name}**\n")

    # --- Assumptions Check ---
    assumptions = test_results.get("assumptions", {})
    if assumptions:
        lines.append("## Assumptions Check\n")
        lines.append("| Assumption | Statistic | p-value | Pass/Fail | Interpretation |")
        lines.append("|------------|-----------|---------|-----------|----------------|")

        for key, val in assumptions.items():
            if isinstance(val, dict) and "statistic" in val:
                stat_str = f"{val['statistic']:.4f}" if val["statistic"] is not None else "N/A"
                p_str = f"{val['p_value']:.4f}" if val["p_value"] is not None else "N/A"
                if val.get("passed") is True:
                    pass_str = "PASS"
                    interp = "Assumption met"
                elif val.get("passed") is False:
                    pass_str = "FAIL"
                    interp = "Assumption violated"
                else:
                    pass_str = "N/A"
                    interp = val.get("note", "Could not assess")
                lines.append(f"| {key} | {stat_str} | {p_str} | {pass_str} | {interp} |")
            elif isinstance(val, dict):
                # Nested normality dict (ANOVA)
                for sub_key, sub_val in val.items():
                    if isinstance(sub_val, dict) and "statistic" in sub_val:
                        stat_str = f"{sub_val['statistic']:.4f}" if sub_val["statistic"] is not None else "N/A"
                        p_str = f"{sub_val['p_value']:.4f}" if sub_val["p_value"] is not None else "N/A"
                        if sub_val.get("passed") is True:
                            pass_str = "PASS"
                            interp = "Assumption met"
                        elif sub_val.get("passed") is False:
                            pass_str = "FAIL"
                            interp = "Assumption violated"
                        else:
                            pass_str = "N/A"
                            interp = sub_val.get("note", "Could not assess")
                        lines.append(f"| {key}_{sub_key} | {stat_str} | {p_str} | {pass_str} | {interp} |")

        lines.append("")

    # --- Results ---
    lines.append("## Results\n")
    stat_val = test_results.get("statistic")
    p_val = test_results.get("p_value")
    if stat_val is not None:
        lines.append(f"- **Test statistic:** {stat_val:.4f}")
    if p_val is not None:
        lines.append(f"- **p-value:** {p_val:.4f}")

    effect = test_results.get("effect_size")
    if effect is not None:
        label = test_results.get("effect_size_label", "")
        lines.append(f"- **Effect size:** {effect:.4f} ({label})")

    ci = test_results.get("ci_95")
    if ci is not None:
        lines.append(f"- **95% CI:** ({ci[0]:.4f}, {ci[1]:.4f})")

    cramers = test_results.get("cramers_v")
    if cramers is not None:
        lines.append(f"- **Cramer's V:** {cramers:.4f}")

    sig = test_results.get("significant")
    if sig is not None:
        lines.append(f"- **Significant:** {'Yes' if sig else 'No'} (alpha = {test_results.get('alpha', 0.05)})")
    lines.append("")

    # --- Interpretation ---
    lines.append("## Interpretation\n")
    if test_type in ("ttest_ind", "ttest_paired"):
        sig_word = "is" if sig else "is not"
        lines.append(
            f"The difference between groups {sig_word} statistically significant "
            f"(p = {p_val:.4f})."
        )
        if effect is not None:
            label = test_results.get("effect_size_label", "")
            lines.append(
                f"The effect size (Cohen's d = {effect:.4f}) suggests a {label} effect."
            )
    elif test_type == "anova":
        sig_word = "is" if sig else "is not"
        lines.append(
            f"The difference among groups {sig_word} statistically significant "
            f"(F = {stat_val:.4f}, p = {p_val:.4f})."
        )
    elif test_type == "chi_square":
        sig_word = "is" if sig else "is not"
        lines.append(
            f"The association between variables {sig_word} statistically significant "
            f"(chi2 = {stat_val:.4f}, p = {p_val:.4f})."
        )
    elif test_type in ("pearson", "spearman"):
        direction = "positive" if stat_val > 0 else "negative"
        strength = "strong" if abs(stat_val) > 0.7 else "moderate" if abs(stat_val) > 0.4 else "weak"
        lines.append(
            f"There is a {strength} {direction} correlation (r = {stat_val:.4f}, p = {p_val:.4f})."
        )
    lines.append("")

    # --- Recommendation ---
    alt = test_results.get("alternative_suggested")
    post_hoc = test_results.get("post_hoc_guidance")
    if alt or post_hoc:
        lines.append("## Recommendation\n")
        if alt:
            lines.append(f"- **Alternative suggested:** {alt}")
        if post_hoc:
            lines.append(f"- **Post-hoc:** {post_hoc}")
        lines.append("")

    return "\n".join(lines)
