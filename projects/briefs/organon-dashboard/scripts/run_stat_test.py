"""Phase 6 (fix-sprint) — direct-Python stat test runner.

Replaces the LLM-routed `/api/data/analyze` path with a deterministic
~5-second subprocess that runs the picked test via scipy, computes
assumption checks + effect sizes, and emits ONE
`{"_artifact":"stat-result", ...}` JSON line on stdout. The dashboard
parses + persists that line; the LLM is reserved for the optional
"Interpret" follow-up button (see /api/data/interpret).

Usage:
    python run_stat_test.py \\
      --data-path <abs csv/xlsx/json> \\
      --run-id stat-YYYYMMDD-XXXXXX \\
      --project-slug <slug> --file-id <data-id> \\
      --test <test_name> --params-json '{...}'

Supported tests (matches lib/data/stat-picker.ts recommendations):
    Group:        ttest_ind, ttest_rel, mannwhitneyu, wilcoxon,
                  anova_oneway, kruskal_wallis, friedman
    Correlation:  pearson, spearman
    Contingency:  chi2_contingency, fisher_exact
    Regression:   linear_regression
    Power:        power_t_test, power_anova, power_correlation, power_chi2

Out of scope (returns clean error):
    logistic_regression — requires statsmodels (not in venv).
"""

import argparse
import json
import math
import sys
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import scipy.stats as stats

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=UserWarning)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _load(path: str) -> pd.DataFrame:
    p = path.lower()
    if p.endswith(".csv"):
        return pd.read_csv(path)
    if p.endswith(".xlsx") or p.endswith(".xls"):
        return pd.read_excel(path)
    if p.endswith(".json"):
        return pd.read_json(path)
    raise ValueError(f"unsupported file format: {path}")


def _err(msg: str, code: int = 1) -> int:
    print(json.dumps({"error": msg}), file=sys.stderr)
    return code


def _verdict(p: float | None, alpha: float = 0.05) -> str:
    if p is None or not math.isfinite(p):
        return "warn"
    return "pass" if p >= alpha else "fail"


def _shapiro(x: np.ndarray) -> dict | None:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 3 or x.size > 5000:
        return None
    try:
        s, p = stats.shapiro(x)
        return {"name": "normality_shapiro", "verdict": _verdict(p),
                "p_value": float(p), "note": f"W={s:.3f}, n={x.size}"}
    except Exception as exc:
        return {"name": "normality_shapiro", "verdict": "warn",
                "note": f"shapiro failed: {exc}"}


def _levene(*groups: np.ndarray) -> dict | None:
    cleaned = [np.asarray(g, dtype=float) for g in groups]
    cleaned = [g[np.isfinite(g)] for g in cleaned]
    if any(g.size < 2 for g in cleaned):
        return None
    try:
        s, p = stats.levene(*cleaned, center="median")
        return {"name": "equal_variance_levene", "verdict": _verdict(p),
                "p_value": float(p), "note": f"W={s:.3f}"}
    except Exception as exc:
        return {"name": "equal_variance_levene", "verdict": "warn",
                "note": f"levene failed: {exc}"}


def _expected_count_check(table: np.ndarray, expected: np.ndarray) -> dict:
    min_exp = float(expected.min()) if expected.size else 0.0
    bad = int((expected < 5).sum())
    if min_exp >= 5:
        verdict = "pass"
    elif min_exp >= 1:
        verdict = "warn"
    else:
        verdict = "fail"
    note = f"min expected={min_exp:.2f}, cells<5={bad}/{expected.size}"
    return {"name": "expected_count_ge_5", "verdict": verdict, "note": note}


def _safe_groups(df: pd.DataFrame, value_col: str, group_col: str
                 ) -> tuple[list[str], list[np.ndarray]]:
    """Return (labels, arrays). Drops NaN rows. Sorted by label."""
    sub = df[[value_col, group_col]].dropna()
    labels = sorted(sub[group_col].astype(str).unique().tolist())
    arrays = [sub.loc[sub[group_col].astype(str) == lab, value_col].to_numpy(dtype=float)
              for lab in labels]
    return labels, arrays


def _result_template(args, params: dict, test_name: str, test_label: str,
                     mode: str) -> dict:
    return {
        "_artifact": "stat-result",
        "schema_version": 1,
        "id": args.run_id,
        "project_slug": args.project_slug,
        "file_id": args.file_id or None,
        "test_name": test_name,
        "test_label": test_label,
        "mode": mode,
        "params": params,
        "test_statistic": None,
        "p_value": None,
        "effect_size": None,
        "n": 0,
        "assumption_checks": [],
        "interpretation": "",
        "code_path": None,
        "results_path": "",
        "library_path": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _format_p(p: float | None) -> str:
    if p is None or not math.isfinite(p):
        return "p=N/A"
    if p < 0.001:
        return "p<0.001"
    return f"p={p:.3f}"


# ---------------------------------------------------------------------------
# Group-comparison tests
# ---------------------------------------------------------------------------

def run_ttest_ind(df: pd.DataFrame, params: dict, args) -> dict:
    value_col = params["value_col"]; group_col = params["group_col"]
    equal_var = bool(params.get("equal_var", False))
    labels, arrays = _safe_groups(df, value_col, group_col)
    if len(arrays) != 2:
        raise ValueError(f"two groups required, got {len(arrays)}")
    a, b = arrays
    if a.size < 2 or b.size < 2:
        raise ValueError("each group needs ≥ 2 observations")
    t, p = stats.ttest_ind(a, b, equal_var=equal_var)
    # Cohen's d (pooled)
    pooled_sd = math.sqrt(((a.size - 1) * a.var(ddof=1) +
                           (b.size - 1) * b.var(ddof=1)) /
                          (a.size + b.size - 2))
    d = (a.mean() - b.mean()) / pooled_sd if pooled_sd > 0 else 0.0
    se_d = math.sqrt((a.size + b.size) / (a.size * b.size) +
                     d * d / (2 * (a.size + b.size)))
    out = _result_template(args, params,
                           "ttest_ind",
                           "Two-sample t-test (Welch)" if not equal_var
                           else "Two-sample t-test",
                           "analyze")
    out.update({
        "test_statistic": float(t), "p_value": float(p),
        "n": int(a.size + b.size),
        "effect_size": {"name": "cohens_d", "value": float(d),
                        "ci_low": float(d - 1.96 * se_d),
                        "ci_high": float(d + 1.96 * se_d)},
        "assumption_checks": [
            c for c in [_shapiro(a), _shapiro(b), _levene(a, b),
                        {"name": "min_group_n",
                         "verdict": "pass" if min(a.size, b.size) >= 30
                                    else "warn" if min(a.size, b.size) >= 10
                                    else "fail",
                         "note": f"n=({a.size}, {b.size})"}]
            if c
        ],
        "interpretation": (
            f"Welch's t-test on '{value_col}' between groups {labels[0]!r} (n={a.size}, "
            f"mean={a.mean():.3f}) and {labels[1]!r} (n={b.size}, mean={b.mean():.3f}): "
            f"t={t:.3f}, {_format_p(p)}, Cohen's d={d:.3f}. "
            + ("Mean difference is statistically significant at α=0.05."
               if p < 0.05 else
               "No significant mean difference at α=0.05.")
        ),
    })
    return out


def run_ttest_rel(df: pd.DataFrame, params: dict, args) -> dict:
    value_col = params["value_col"]; group_col = params["group_col"]
    labels, arrays = _safe_groups(df, value_col, group_col)
    if len(arrays) != 2:
        raise ValueError(f"two groups required, got {len(arrays)}")
    a, b = arrays
    if a.size != b.size:
        raise ValueError(f"paired t-test requires equal-length groups, got "
                         f"({a.size}, {b.size}). Use ttest_ind for unpaired.")
    if a.size < 2:
        raise ValueError("paired t-test needs ≥ 2 paired observations")
    t, p = stats.ttest_rel(a, b)
    diff = a - b
    sd_diff = diff.std(ddof=1)
    d = diff.mean() / sd_diff if sd_diff > 0 else 0.0
    out = _result_template(args, params, "ttest_rel", "Paired t-test", "analyze")
    out.update({
        "test_statistic": float(t), "p_value": float(p),
        "n": int(a.size),
        "effect_size": {"name": "cohens_dz", "value": float(d)},
        "assumption_checks": [c for c in [_shapiro(diff)] if c],
        "interpretation": (
            f"Paired t-test on '{value_col}' across {labels!r}: t={t:.3f}, {_format_p(p)}, "
            f"Cohen's dz={d:.3f}, mean diff={diff.mean():.3f}. "
            + ("Within-pair difference is significant at α=0.05."
               if p < 0.05 else "No significant within-pair difference.")
        ),
    })
    return out


def run_mannwhitneyu(df: pd.DataFrame, params: dict, args) -> dict:
    value_col = params["value_col"]; group_col = params["group_col"]
    labels, arrays = _safe_groups(df, value_col, group_col)
    if len(arrays) != 2:
        raise ValueError(f"two groups required, got {len(arrays)}")
    a, b = arrays
    if a.size < 1 or b.size < 1:
        raise ValueError("each group needs ≥ 1 observation")
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    n1, n2 = a.size, b.size
    rank_biserial = 1.0 - (2.0 * u) / (n1 * n2)
    out = _result_template(args, params, "mannwhitneyu", "Mann–Whitney U", "analyze")
    out.update({
        "test_statistic": float(u), "p_value": float(p), "n": int(n1 + n2),
        "effect_size": {"name": "rank_biserial", "value": float(rank_biserial)},
        "assumption_checks": [{
            "name": "min_group_n",
            "verdict": "pass" if min(n1, n2) >= 20 else "warn",
            "note": f"n=({n1}, {n2})",
        }],
        "interpretation": (
            f"Mann–Whitney U test on '{value_col}' between {labels[0]!r} (n={n1}) "
            f"and {labels[1]!r} (n={n2}): U={u:.0f}, {_format_p(p)}, "
            f"rank-biserial r={rank_biserial:.3f}. "
            + ("Distribution shift is significant at α=0.05."
               if p < 0.05 else "No significant rank shift between groups.")
        ),
    })
    return out


def run_wilcoxon(df: pd.DataFrame, params: dict, args) -> dict:
    value_col = params["value_col"]; group_col = params["group_col"]
    labels, arrays = _safe_groups(df, value_col, group_col)
    if len(arrays) != 2:
        raise ValueError(f"two groups required, got {len(arrays)}")
    a, b = arrays
    if a.size != b.size or a.size < 1:
        raise ValueError(f"Wilcoxon needs equal-length paired groups, got ({a.size}, {b.size})")
    w, p = stats.wilcoxon(a, b)
    out = _result_template(args, params, "wilcoxon", "Wilcoxon signed-rank", "analyze")
    out.update({
        "test_statistic": float(w), "p_value": float(p), "n": int(a.size),
        "interpretation": (
            f"Wilcoxon signed-rank on '{value_col}' across {labels!r} (n={a.size} pairs): "
            f"W={w:.0f}, {_format_p(p)}. "
            + ("Within-pair median shift is significant at α=0.05."
               if p < 0.05 else "No significant within-pair median shift.")
        ),
    })
    return out


def run_anova_oneway(df: pd.DataFrame, params: dict, args) -> dict:
    value_col = params["value_col"]; group_col = params["group_col"]
    labels, arrays = _safe_groups(df, value_col, group_col)
    if len(arrays) < 2:
        raise ValueError(f"need ≥ 2 groups, got {len(arrays)}")
    if any(a.size < 2 for a in arrays):
        raise ValueError("each group needs ≥ 2 observations")
    f, p = stats.f_oneway(*arrays)
    # Eta-squared
    grand = np.concatenate(arrays).mean()
    ss_between = sum(a.size * (a.mean() - grand) ** 2 for a in arrays)
    ss_total = sum(((a - grand) ** 2).sum() for a in arrays)
    eta2 = ss_between / ss_total if ss_total > 0 else 0.0
    n_total = sum(a.size for a in arrays)
    checks = [c for c in [_shapiro(np.concatenate(arrays)),
                          _levene(*arrays)] if c]
    out = _result_template(args, params, "anova_oneway", "One-way ANOVA", "analyze")
    out.update({
        "test_statistic": float(f), "p_value": float(p), "n": int(n_total),
        "effect_size": {"name": "eta_squared", "value": float(eta2)},
        "assumption_checks": checks,
        "interpretation": (
            f"One-way ANOVA on '{value_col}' across {len(arrays)} groups "
            f"({', '.join(labels)}): F={f:.3f}, {_format_p(p)}, η²={eta2:.3f}. "
            + ("Group means differ at α=0.05; consider Tukey HSD post-hoc."
               if p < 0.05 else "Group means do not differ significantly.")
        ),
    })
    return out


def run_kruskal_wallis(df: pd.DataFrame, params: dict, args) -> dict:
    value_col = params["value_col"]; group_col = params["group_col"]
    labels, arrays = _safe_groups(df, value_col, group_col)
    if len(arrays) < 2:
        raise ValueError(f"need ≥ 2 groups, got {len(arrays)}")
    h, p = stats.kruskal(*arrays)
    n_total = sum(a.size for a in arrays)
    eta2_h = (h - len(arrays) + 1) / (n_total - len(arrays)) if n_total > len(arrays) else 0.0
    out = _result_template(args, params, "kruskal_wallis", "Kruskal–Wallis", "analyze")
    out.update({
        "test_statistic": float(h), "p_value": float(p), "n": int(n_total),
        "effect_size": {"name": "epsilon_sq_h", "value": float(eta2_h)},
        "interpretation": (
            f"Kruskal–Wallis on '{value_col}' across {len(arrays)} groups "
            f"({', '.join(labels)}): H={h:.3f}, {_format_p(p)}, ε²={eta2_h:.3f}. "
            + ("Distribution shift across groups is significant at α=0.05."
               if p < 0.05 else "No significant rank shift across groups.")
        ),
    })
    return out


def run_friedman(df: pd.DataFrame, params: dict, args) -> dict:
    value_col = params["value_col"]; group_col = params["group_col"]
    labels, arrays = _safe_groups(df, value_col, group_col)
    if len(arrays) < 3:
        raise ValueError(f"Friedman needs ≥ 3 conditions, got {len(arrays)}")
    n = arrays[0].size
    if any(a.size != n for a in arrays):
        raise ValueError("Friedman needs equal-length groups (same subjects across conditions)")
    chi2, p = stats.friedmanchisquare(*arrays)
    out = _result_template(args, params, "friedman", "Friedman test", "analyze")
    out.update({
        "test_statistic": float(chi2), "p_value": float(p), "n": int(n),
        "interpretation": (
            f"Friedman test on '{value_col}' across {len(arrays)} conditions "
            f"({', '.join(labels)}, n={n}): χ²={chi2:.3f}, {_format_p(p)}. "
            + ("Repeated-measure rank shift is significant at α=0.05."
               if p < 0.05 else "No significant rank shift across conditions.")
        ),
    })
    return out


# ---------------------------------------------------------------------------
# Correlation tests
# ---------------------------------------------------------------------------

def _correlation(df, params, args, kind: str) -> dict:
    x_col = params["x_col"]; y_col = params["y_col"]
    sub = df[[x_col, y_col]].dropna()
    if sub.shape[0] < 3:
        raise ValueError(f"correlation needs ≥ 3 paired observations, got {sub.shape[0]}")
    x = sub[x_col].to_numpy(dtype=float)
    y = sub[y_col].to_numpy(dtype=float)
    if kind == "pearson":
        r, p = stats.pearsonr(x, y)
        label = "Pearson correlation"; eff_name = "pearson_r"
        # Fisher z 95% CI
        if abs(r) < 1:
            z = 0.5 * math.log((1 + r) / (1 - r))
            se = 1.0 / math.sqrt(x.size - 3) if x.size > 3 else float("nan")
            ci_low_z, ci_high_z = z - 1.96 * se, z + 1.96 * se
            ci_low = (math.exp(2 * ci_low_z) - 1) / (math.exp(2 * ci_low_z) + 1)
            ci_high = (math.exp(2 * ci_high_z) - 1) / (math.exp(2 * ci_high_z) + 1)
        else:
            ci_low = ci_high = r
        eff = {"name": eff_name, "value": float(r),
               "ci_low": float(ci_low), "ci_high": float(ci_high)}
        checks = [c for c in [_shapiro(x), _shapiro(y)] if c]
    else:
        r, p = stats.spearmanr(x, y)
        label = "Spearman rank correlation"; eff_name = "spearman_rho"
        eff = {"name": eff_name, "value": float(r)}
        checks = []
    out = _result_template(args, params, kind, label, "analyze")
    out.update({
        "test_statistic": float(r), "p_value": float(p), "n": int(x.size),
        "effect_size": eff, "assumption_checks": checks,
        "interpretation": (
            f"{label} between '{x_col}' and '{y_col}' (n={x.size}): "
            f"r={r:.3f}, {_format_p(p)}. "
            + ("Association is statistically significant at α=0.05."
               if p < 0.05 else "No significant association at α=0.05.")
        ),
    })
    return out


def run_pearson(df, params, args): return _correlation(df, params, args, "pearson")
def run_spearman(df, params, args): return _correlation(df, params, args, "spearman")


# ---------------------------------------------------------------------------
# Contingency tests
# ---------------------------------------------------------------------------

def run_chi2_contingency(df, params, args) -> dict:
    row_col = params["row_col"]; col_col = params["col_col"]
    sub = df[[row_col, col_col]].dropna()
    table = pd.crosstab(sub[row_col].astype(str), sub[col_col].astype(str))
    if table.shape[0] < 2 or table.shape[1] < 2:
        raise ValueError(f"chi-squared needs at least 2x2, got {table.shape}")
    chi2, p, dof, expected = stats.chi2_contingency(table.to_numpy())
    n = int(table.to_numpy().sum())
    cramers_v = math.sqrt(chi2 / (n * (min(table.shape) - 1))) if n > 0 else 0.0
    out = _result_template(args, params, "chi2_contingency", "Chi-squared test", "analyze")
    out.update({
        "test_statistic": float(chi2), "p_value": float(p), "n": n,
        "effect_size": {"name": "cramers_v", "value": float(cramers_v)},
        "assumption_checks": [_expected_count_check(table.to_numpy(), expected)],
        "interpretation": (
            f"χ² test on {row_col!r} × {col_col!r} ({table.shape[0]}×{table.shape[1]} table, "
            f"n={n}): χ²={chi2:.3f}, df={dof}, {_format_p(p)}, Cramér's V={cramers_v:.3f}. "
            + ("Association is significant at α=0.05."
               if p < 0.05 else "No significant association at α=0.05.")
        ),
    })
    return out


def run_fisher_exact(df, params, args) -> dict:
    row_col = params["row_col"]; col_col = params["col_col"]
    sub = df[[row_col, col_col]].dropna()
    table = pd.crosstab(sub[row_col].astype(str), sub[col_col].astype(str))
    if table.shape != (2, 2):
        raise ValueError(f"Fisher exact needs 2x2 table, got {table.shape}")
    odds_ratio, p = stats.fisher_exact(table.to_numpy())
    n = int(table.to_numpy().sum())
    out = _result_template(args, params, "fisher_exact", "Fisher's exact test", "analyze")
    out.update({
        "test_statistic": float(odds_ratio), "p_value": float(p), "n": n,
        "effect_size": {"name": "odds_ratio", "value": float(odds_ratio)},
        "interpretation": (
            f"Fisher's exact test on 2×2 contingency (n={n}): "
            f"odds ratio={odds_ratio:.3f}, {_format_p(p)}. "
            + ("Association is significant at α=0.05."
               if p < 0.05 else "No significant association at α=0.05.")
        ),
    })
    return out


# ---------------------------------------------------------------------------
# Linear regression (multi-predictor OLS without statsmodels)
# ---------------------------------------------------------------------------

def _ols_r2(X: np.ndarray, y: np.ndarray) -> float:
    """OLS R² via lstsq — used by Breusch-Pagan + VIF auxiliary regressions."""
    if X.shape[0] <= X.shape[1]:
        return float("nan")
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ beta
    rss = float(((y - y_hat) ** 2).sum())
    tss = float(((y - y.mean()) ** 2).sum())
    return 1 - rss / tss if tss > 0 else 0.0


def _regression_diagnostics(
    X: np.ndarray,
    resid: np.ndarray,
    pred_names: list[str],
    n: int,
    k: int,
) -> list[dict]:
    """Phase 12b (v1.0.1) — D-9 four assumption diagnostics for linear
    regression. Implemented in pure scipy + numpy — `statsmodels` is
    intentionally NOT in the dashboard's venv (see module docstring).

    Returns a list of assumption_check dicts (PASS/WARN/FAIL/null) ready
    to merge into the StatResultArtifact.assumption_checks list. The list
    schema mirrors the existing ANOVA path (`name`, `verdict`, optional
    `p_value`, optional `note`) so the existing renderer surfaces them
    without a card-level change.

    Pre-conditions caller has already validated:
      • n >= k + 2 (otherwise residual df is degenerate)
      • X[:, 0] is the intercept column

    Each diagnostic returns null verdict ("warn" with explanatory note) on
    its own degeneracy rather than crashing the run.
    """
    out: list[dict] = []

    # 1) Breusch-Pagan (homoscedasticity).
    #    Auxiliary regression: regress squared residuals on the original
    #    design matrix; under H₀ (homoscedastic errors), n*R²_aux is
    #    asymptotically chi²(k) where k = #non-intercept regressors.
    try:
        resid_sq = resid ** 2
        if k >= 1 and resid_sq.size >= k + 2 and float(resid_sq.var()) > 0:
            r2_bp = _ols_r2(X, resid_sq)
            if math.isfinite(r2_bp):
                lm_stat = n * r2_bp
                bp_p = float(1 - stats.chi2.cdf(lm_stat, k))
                out.append({
                    "name": "homoscedasticity_breusch_pagan",
                    "verdict": _verdict(bp_p),
                    "p_value": bp_p,
                    "note": f"LM={lm_stat:.3f}, df={k}",
                })
            else:
                out.append({"name": "homoscedasticity_breusch_pagan",
                            "verdict": "warn",
                            "note": "auxiliary regression degenerate"})
        else:
            out.append({"name": "homoscedasticity_breusch_pagan",
                        "verdict": "warn",
                        "note": f"insufficient n (need ≥ {k + 2})"})
    except Exception as exc:
        out.append({"name": "homoscedasticity_breusch_pagan",
                    "verdict": "warn",
                    "note": f"breusch-pagan failed: {exc}"})

    # 2) Shapiro-Wilk on residuals (normality).
    sh = _shapiro(resid)
    if sh is not None:
        # Tag as residual normality so the user knows what was tested.
        sh = {**sh, "name": "residual_normality_shapiro"}
        out.append(sh)
    else:
        out.append({"name": "residual_normality_shapiro",
                    "verdict": "warn",
                    "note": f"shapiro requires 3 ≤ n ≤ 5000 (n={resid.size})"})

    # 3) Durbin-Watson (no autocorrelation).
    #    DW = Σ(r_t - r_{t-1})² / Σr_t². No statsmodels needed.
    try:
        if resid.size >= 2 and float((resid ** 2).sum()) > 0:
            num = float(((np.diff(resid)) ** 2).sum())
            den = float((resid ** 2).sum())
            dw = num / den
            passed = 1.5 <= dw <= 2.5
            out.append({
                "name": "no_autocorrelation_durbin_watson",
                "verdict": "pass" if passed else "warn",
                "note": f"DW={dw:.3f} (1.5 ≤ DW ≤ 2.5 → no autocorrelation)",
            })
        else:
            out.append({"name": "no_autocorrelation_durbin_watson",
                        "verdict": "warn",
                        "note": "residuals too small for Durbin-Watson"})
    except Exception as exc:
        out.append({"name": "no_autocorrelation_durbin_watson",
                    "verdict": "warn",
                    "note": f"durbin-watson failed: {exc}"})

    # 4) VIF (multicollinearity).
    #    For each non-intercept predictor i, regress it on the OTHER
    #    non-intercept predictors; VIF_i = 1 / (1 - R²_i). Max VIF < 10
    #    is the typical pass threshold (some literature recommends 5).
    #    Single-predictor regression has no other predictors to test
    #    against — emit null with the documented note (per brief §5.3).
    try:
        # Drop intercept column for the auxiliary regressions.
        intercept_col = 0  # X[:, 0] is the intercept by construction
        non_int_cols = [j for j in range(X.shape[1]) if j != intercept_col]
        if len(non_int_cols) < 2:
            out.append({"name": "no_multicollinearity_vif",
                        "verdict": "pass",
                        "note": "single predictor"})
        else:
            vifs: list[tuple[str, float]] = []
            for j in non_int_cols:
                others = [c for c in non_int_cols if c != j]
                X_other = np.column_stack([X[:, intercept_col], X[:, others]])
                y_j = X[:, j].astype(float)
                # Constant predictor → R²=0 → VIF=1; numpy lstsq handles it.
                if float(np.var(y_j)) == 0.0:
                    vifs.append((pred_names[j], 1.0))
                    continue
                r2_j = _ols_r2(X_other, y_j)
                if not math.isfinite(r2_j) or r2_j >= 1.0:
                    vifs.append((pred_names[j], float("inf")))
                else:
                    vifs.append((pred_names[j], 1.0 / (1.0 - r2_j)))
            max_name, max_vif = max(vifs, key=lambda t: t[1]) if vifs else (None, 0.0)
            passed = math.isfinite(max_vif) and max_vif < 10.0
            note = (f"max VIF={max_vif:.2f} ({max_name})"
                    if max_name is not None and math.isfinite(max_vif)
                    else "max VIF=inf — perfect collinearity detected")
            out.append({
                "name": "no_multicollinearity_vif",
                "verdict": "pass" if passed else "warn",
                "note": note,
            })
    except Exception as exc:
        out.append({"name": "no_multicollinearity_vif",
                    "verdict": "warn",
                    "note": f"vif failed: {exc}"})

    return out


def run_linear_regression(df, params, args) -> dict:
    target = params["target_col"]
    preds = list(params["predictor_cols"])
    if not preds:
        raise ValueError("at least one predictor required")
    sub = df[[target] + preds].dropna()
    n = sub.shape[0]
    k = len(preds)
    if n <= k + 1:
        raise ValueError(f"need n > predictors+1; got n={n}, predictors={k}")
    # Build design matrix; categorical predictors get one-hot encoded.
    X_parts = [pd.Series(1.0, index=sub.index, name="(Intercept)")]
    for c in preds:
        col = sub[c]
        if pd.api.types.is_numeric_dtype(col):
            X_parts.append(col.astype(float).rename(c))
        else:
            dummies = pd.get_dummies(col.astype(str), prefix=c, drop_first=True, dtype=float)
            for col_name in dummies.columns:
                X_parts.append(dummies[col_name])
    X = pd.concat(X_parts, axis=1)
    y = sub[target].astype(float).to_numpy()
    Xv = X.to_numpy(dtype=float)
    # OLS via lstsq
    beta, *_ = np.linalg.lstsq(Xv, y, rcond=None)
    y_hat = Xv @ beta
    resid = y - y_hat
    rss = float((resid ** 2).sum())
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - rss / tss if tss > 0 else 0.0
    df_resid = n - Xv.shape[1]
    sigma2 = rss / df_resid if df_resid > 0 else float("nan")
    # Coefficient SEs from (X'X)^-1 * sigma2
    try:
        xtx_inv = np.linalg.pinv(Xv.T @ Xv)
        se = np.sqrt(np.diag(xtx_inv) * sigma2)
        t_stats = beta / np.where(se > 0, se, np.nan)
        p_vals = 2 * (1 - stats.t.cdf(np.abs(t_stats), df_resid))
    except Exception:
        se = np.full_like(beta, float("nan"))
        t_stats = np.full_like(beta, float("nan"))
        p_vals = np.full_like(beta, float("nan"))
    # Overall F-test
    df_model = Xv.shape[1] - 1
    if df_model > 0 and df_resid > 0 and tss > 0:
        f_stat = (r2 / df_model) / ((1 - r2) / df_resid)
        f_p = float(1 - stats.f.cdf(f_stat, df_model, df_resid))
    else:
        f_stat = float("nan"); f_p = float("nan")
    coef_table = []
    for name, b, s, t, pv in zip(X.columns, beta, se, t_stats, p_vals):
        coef_table.append({
            "name": name, "estimate": float(b), "std_error": float(s),
            "t_statistic": float(t) if math.isfinite(t) else None,
            "p_value": float(pv) if math.isfinite(pv) else None,
        })
    # Phase 12b (v1.0.1) — D-9 four assumption diagnostics for OLS.
    # k_predictors counts the non-intercept regressors (after dummy
    # expansion of categoricals); guards against the n ≤ k+1 degenerate
    # case so the per-diagnostic n-checks have a stable contract.
    k_predictors = max(int(Xv.shape[1] - 1), 1)
    diagnostics = _regression_diagnostics(
        X=Xv, resid=resid, pred_names=list(X.columns),
        n=int(n), k=k_predictors,
    )

    out = _result_template(args, params, "linear_regression",
                           "Linear regression (OLS)", "analyze")
    out.update({
        "test_statistic": float(f_stat) if math.isfinite(f_stat) else None,
        "p_value": float(f_p) if math.isfinite(f_p) else None,
        "n": int(n),
        "effect_size": {"name": "r_squared", "value": float(r2)},
        "assumption_checks": diagnostics,
        "params": {**params, "coefficients": coef_table,
                   "df_model": int(df_model), "df_resid": int(df_resid)},
        "interpretation": (
            f"OLS regression of '{target}' on {preds!r} (n={n}): "
            f"R²={r2:.3f}, F({df_model}, {df_resid})={f_stat:.3f}, {_format_p(f_p)}. "
            + ("Overall fit is significant at α=0.05; inspect per-coefficient p-values."
               if math.isfinite(f_p) and f_p < 0.05 else
               "Overall fit is not significant at α=0.05.")
        ),
    })
    return out


# ---------------------------------------------------------------------------
# Power analysis (closed-form via scipy non-central distributions)
# ---------------------------------------------------------------------------

def _power_t_two_sample(d: float, n_per_group: int, alpha: float) -> float:
    df = 2 * n_per_group - 2
    if df < 1: return float("nan")
    nc = d * math.sqrt(n_per_group / 2.0)
    crit = stats.t.ppf(1 - alpha / 2, df)
    return float(1 - stats.nct.cdf(crit, df, nc) + stats.nct.cdf(-crit, df, nc))


def _power_anova(f: float, k: int, n_per_group: int, alpha: float) -> float:
    df_n = k - 1
    df_d = (n_per_group * k) - k
    if df_d < 1 or df_n < 1: return float("nan")
    nc = f * f * n_per_group * k
    crit = stats.f.ppf(1 - alpha, df_n, df_d)
    return float(1 - stats.ncf.cdf(crit, df_n, df_d, nc))


def _power_correlation(r: float, n: int, alpha: float) -> float:
    if n <= 3 or abs(r) >= 1: return float("nan")
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    return float(stats.norm.cdf(z / se - z_alpha) +
                 stats.norm.cdf(-z / se - z_alpha))


def _power_chi2(w: float, df: int, n: int, alpha: float) -> float:
    if df < 1 or n < df + 1: return float("nan")
    nc = (w ** 2) * n
    crit = stats.chi2.ppf(1 - alpha, df)
    return float(1 - stats.ncx2.cdf(crit, df, nc))


def run_power(df, params, args) -> dict:
    test_kind = params["test_kind"]
    effect = float(params["effect_size"])
    alpha = float(params["alpha"])
    target_power = params.get("power_target")
    n_input = params.get("n")

    def power_at(n: int) -> float:
        if test_kind == "t-test": return _power_t_two_sample(effect, n, alpha)
        if test_kind == "anova": return _power_anova(effect, 3, n, alpha)
        if test_kind == "correlation": return _power_correlation(effect, n, alpha)
        if test_kind == "chi2": return _power_chi2(effect, 1, n, alpha)
        raise ValueError(f"unknown power test_kind: {test_kind}")

    if n_input is not None:
        n = int(n_input)
        achieved = power_at(n)
        statistic = float(achieved)
        interp = (f"Power analysis ({test_kind}): given effect={effect}, α={alpha}, "
                  f"n={n}, achieved power = {achieved:.3f}.")
    else:
        target = float(target_power)
        # Binary search for smallest n meeting target.
        lo, hi = 4, 100_000
        # Verify monotonicity by checking hi:
        if power_at(hi) < target:
            n = hi
            achieved = power_at(hi)
            interp = (f"Power analysis ({test_kind}): even n={hi} achieves only "
                      f"power={achieved:.3f} < target {target}; increase effect or α.")
        else:
            while lo < hi:
                mid = (lo + hi) // 2
                if power_at(mid) >= target: hi = mid
                else: lo = mid + 1
            n = lo
            achieved = power_at(n)
            interp = (f"Power analysis ({test_kind}): required n={n} for power≥{target} "
                      f"with effect={effect}, α={alpha} (achieved={achieved:.3f}).")
        statistic = float(n)

    out = _result_template(args, params, f"power_{test_kind.replace('-', '_')}",
                           f"Power analysis ({test_kind})", "power")
    out.update({
        "test_statistic": statistic,
        "p_value": None,
        "n": int(n_input) if n_input is not None else int(statistic),
        "effect_size": {"name": "achieved_power", "value": float(achieved)},
        "interpretation": interp,
    })
    return out


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

DISPATCH = {
    "ttest_ind": run_ttest_ind,
    "ttest_rel": run_ttest_rel,
    "mannwhitneyu": run_mannwhitneyu,
    "wilcoxon": run_wilcoxon,
    "anova_oneway": run_anova_oneway,
    "kruskal_wallis": run_kruskal_wallis,
    "friedman": run_friedman,
    "pearson": run_pearson,
    "spearman": run_spearman,
    "chi2_contingency": run_chi2_contingency,
    "fisher_exact": run_fisher_exact,
    "linear_regression": run_linear_regression,
    "power_t_test": run_power,
    "power_anova": run_power,
    "power_correlation": run_power,
    "power_chi2": run_power,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", required=False, default="",
                        help="absolute path to data file (csv/xlsx/json); not required for power tests")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-slug", required=True)
    parser.add_argument("--file-id", default="")
    parser.add_argument("--test", required=True, dest="test_name")
    parser.add_argument("--params-json", required=True)
    args = parser.parse_args()

    if args.test_name == "logistic_regression":
        return _err(
            "logistic_regression requires statsmodels (not available in the dashboard's "
            "Python venv). Install with `pip install statsmodels` or use the legacy LLM "
            "Interpret button."
        )
    if args.test_name not in DISPATCH:
        return _err(f"unsupported test: {args.test_name}")

    try:
        params = json.loads(args.params_json)
    except json.JSONDecodeError as exc:
        return _err(f"invalid --params-json: {exc}")

    is_power = args.test_name.startswith("power_")
    if not is_power:
        if not args.data_path:
            return _err("--data-path is required for non-power tests")
        try:
            df = _load(args.data_path)
        except Exception as exc:
            return _err(f"failed to load {args.data_path}: {exc}")
    else:
        df = pd.DataFrame()

    try:
        artifact = DISPATCH[args.test_name](df, params, args)
    except (ValueError, KeyError) as exc:
        # Param / data-shape errors are user input problems → exit 2 → HTTP 400.
        # KeyError surfaces from pandas when a referenced column is absent.
        msg = str(exc).strip("'\"")
        return _err(msg, code=2)
    except Exception as exc:
        return _err(f"{args.test_name} failed: {exc}", code=1)

    print(json.dumps(artifact, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
