"""Hypothesis & Experiment Design backend -- power analysis, evidence spectrum,
data pattern extraction, and report generation for sci-hypothesis skill.

Per D-06: Power analysis using scipy non-central distributions (no statsmodels).
Per D-09: Reuses data_ops.run_statistical_test() and run_regression().
Per D-10: Five-level evidence spectrum classification.
Per D-12: All validation operations logged via repro_logger.
"""

import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import nct, ncf, ncx2, norm, pearsonr, spearmanr

# ---------------------------------------------------------------------------
# Cross-skill imports (Pattern 2 from 05-RESEARCH.md)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[4]
assert (PROJECT_ROOT / "repro").exists(), f"PROJECT_ROOT resolution failed: {PROJECT_ROOT}"

sys.path.insert(0, str(PROJECT_ROOT))
from repro.repro_logger import log_operation

DATA_SCRIPTS = PROJECT_ROOT / ".claude" / "skills" / "sci-data-analysis" / "scripts"
sys.path.insert(0, str(DATA_SCRIPTS))
from data_ops import (
    run_statistical_test,
    run_regression,
    load_and_profile,
    _cohens_d,
    _shapiro_check,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ALPHA = 0.05
DEFAULT_POWER = 0.80


# ---------------------------------------------------------------------------
# Power Analysis (HYPO-05, D-06)
# ---------------------------------------------------------------------------

def ttest_power_analysis(
    effect_size: float,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
    ratio: float = 1.0,
) -> dict:
    """Compute required sample size for independent two-sample t-test.

    Uses normal approximation for initial estimate, then refines with
    exact non-central t distribution.

    Args:
        effect_size: Cohen's d.
        alpha: Significance level (default 0.05).
        power: Desired statistical power (default 0.80).
        ratio: n2/n1 ratio (default 1.0 = equal groups).

    Returns:
        Dict with n1, n2, total_n, actual_power, and sensitivity_table.
    """
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    n1_approx = math.ceil(
        (1 + 1 / ratio) * ((z_alpha + z_beta) / effect_size) ** 2
    )

    def _power_at_n(n1: int) -> float:
        n2 = math.ceil(n1 * ratio)
        df = n1 + n2 - 2
        ncp = effect_size * math.sqrt(n1 * n2 / (n1 + n2))
        t_crit = nct.ppf(1 - alpha / 2, df, 0)
        return 1 - nct.cdf(t_crit, df, ncp) + nct.cdf(-t_crit, df, ncp)

    # Binary search from approximate value
    n1 = max(n1_approx - 5, 3)
    while _power_at_n(n1) < power:
        n1 += 1
    n2 = math.ceil(n1 * ratio)

    # Sensitivity table
    sensitivity = []
    effect_sizes = sorted(set([0.2, 0.5, 0.8, effect_size]))
    for d in effect_sizes:
        for p in [0.70, 0.80, 0.90, 0.95]:
            z_b = norm.ppf(p)
            n_est = math.ceil(
                (1 + 1 / ratio) * ((z_alpha + z_b) / d) ** 2
            )
            sensitivity.append({
                "effect_size": d,
                "power": p,
                "n_per_group": n_est,
            })

    return {
        "n1": n1,
        "n2": n2,
        "total_n": n1 + n2,
        "actual_power": round(_power_at_n(n1), 4),
        "sensitivity_table": sensitivity,
    }


def anova_power_analysis(
    effect_size: float,
    k_groups: int,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> dict:
    """Compute required sample size for one-way ANOVA.

    Uses non-central F distribution for exact power calculation.

    Args:
        effect_size: Cohen's f.
        k_groups: Number of groups.
        alpha: Significance level (default 0.05).
        power: Desired statistical power (default 0.80).

    Returns:
        Dict with n_per_group, total_n, k_groups, actual_power, sensitivity_table.
    """
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)

    # Approximate n per group
    n_approx = max(math.ceil(((z_alpha + z_beta) / effect_size) ** 2 / k_groups), 3)

    def _power_at_n(n: int) -> float:
        df1 = k_groups - 1
        df2 = k_groups * (n - 1)
        ncp = effect_size ** 2 * n * k_groups
        f_crit = ncf.ppf(1 - alpha, df1, df2, 0)
        return 1 - ncf.cdf(f_crit, df1, df2, ncp)

    n = max(n_approx - 5, 3)
    while _power_at_n(n) < power:
        n += 1

    # Sensitivity table
    sensitivity = []
    effect_sizes = sorted(set([0.10, 0.25, 0.40, effect_size]))
    for f_es in effect_sizes:
        for p in [0.70, 0.80, 0.90, 0.95]:
            z_b = norm.ppf(p)
            n_est = max(
                math.ceil(((z_alpha + z_b) / f_es) ** 2 / k_groups), 3
            )
            sensitivity.append({
                "effect_size": f_es,
                "power": p,
                "n_per_group": n_est,
            })

    return {
        "n_per_group": n,
        "total_n": n * k_groups,
        "k_groups": k_groups,
        "actual_power": round(_power_at_n(n), 4),
        "sensitivity_table": sensitivity,
    }


def chisq_power_analysis(
    effect_size: float,
    df: int,
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
) -> dict:
    """Compute required sample size for chi-square test.

    Uses non-central chi-square distribution for exact power calculation.

    Args:
        effect_size: Cohen's w.
        df: Degrees of freedom.
        alpha: Significance level (default 0.05).
        power: Desired statistical power (default 0.80).

    Returns:
        Dict with total_n, df, actual_power, sensitivity_table.
    """
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    n_approx = max(math.ceil(((z_alpha + z_beta) / effect_size) ** 2), 10)

    def _power_at_n(n: int) -> float:
        ncp = effect_size ** 2 * n
        chi2_crit = ncx2.ppf(1 - alpha, df, 0)
        return 1 - ncx2.cdf(chi2_crit, df, ncp)

    n = max(n_approx - 5, 10)
    while _power_at_n(n) < power:
        n += 1

    # Sensitivity table
    sensitivity = []
    effect_sizes = sorted(set([0.1, 0.3, 0.5, effect_size]))
    for w in effect_sizes:
        for p in [0.70, 0.80, 0.90, 0.95]:
            z_b = norm.ppf(p)
            n_est = max(math.ceil(((z_alpha + z_b) / w) ** 2), 10)
            sensitivity.append({
                "effect_size": w,
                "power": p,
                "total_n": n_est,
            })

    return {
        "total_n": n,
        "df": df,
        "actual_power": round(_power_at_n(n), 4),
        "sensitivity_table": sensitivity,
    }


# ---------------------------------------------------------------------------
# Evidence Spectrum Classification (HYPO-04, D-10)
# ---------------------------------------------------------------------------

def _build_rationale(
    verdict: str,
    p_value: float,
    effect_mag: float,
    ci_includes_zero: bool,
) -> str:
    """Build a plain-English rationale for the evidence verdict."""
    parts = []

    if p_value < 0.01:
        parts.append(f"p-value ({p_value:.4f}) indicates strong statistical significance")
    elif p_value < 0.05:
        parts.append(f"p-value ({p_value:.4f}) indicates statistical significance")
    elif p_value < 0.10:
        parts.append(f"p-value ({p_value:.4f}) is marginally significant")
    else:
        parts.append(f"p-value ({p_value:.4f}) does not reach statistical significance")

    if effect_mag >= 0.8:
        parts.append(f"effect size ({effect_mag:.2f}) is large")
    elif effect_mag >= 0.5:
        parts.append(f"effect size ({effect_mag:.2f}) is medium")
    elif effect_mag >= 0.2:
        parts.append(f"effect size ({effect_mag:.2f}) is small")
    else:
        parts.append(f"effect size ({effect_mag:.2f}) is negligible")

    if ci_includes_zero:
        parts.append("confidence interval includes zero")
    else:
        parts.append("confidence interval excludes zero")

    return f"{verdict}: {'; '.join(parts)}."


def classify_evidence(
    p_value: float,
    effect_size: float,
    ci_lower: float,
    ci_upper: float,
) -> dict:
    """Classify hypothesis support on a five-level evidence spectrum.

    Uses p-value, effect size magnitude, and confidence interval to
    produce a nuanced verdict rather than binary pass/fail.

    Args:
        p_value: Statistical test p-value.
        effect_size: Effect size measure (e.g., Cohen's d, r).
        ci_lower: Lower bound of 95% confidence interval.
        ci_upper: Upper bound of 95% confidence interval.

    Returns:
        Dict with verdict, p_value, effect_size, ci_95, and rationale.
    """
    effect_mag = abs(effect_size)
    ci_includes_zero = ci_lower <= 0 <= ci_upper

    if p_value < 0.01 and effect_mag >= 0.5 and not ci_includes_zero:
        verdict = "Strong Support"
    elif p_value < 0.05 and effect_mag >= 0.2 and not ci_includes_zero:
        verdict = "Moderate Support"
    elif p_value >= 0.70 and effect_mag < 0.1 and ci_includes_zero:
        # Very high p-value + negligible effect + CI includes zero
        verdict = "Strong Against"
    elif p_value >= 0.05 and ci_includes_zero:
        if effect_mag < 0.2:
            verdict = "Moderate Against"
        else:
            verdict = "Inconclusive"
    else:
        verdict = "Inconclusive"

    return {
        "verdict": verdict,
        "p_value": p_value,
        "effect_size": effect_size,
        "ci_95": (ci_lower, ci_upper),
        "rationale": _build_rationale(verdict, p_value, effect_mag, ci_includes_zero),
    }


# ---------------------------------------------------------------------------
# Data Pattern Analysis (HYPO-01)
# ---------------------------------------------------------------------------

def analyze_patterns(filepath: str) -> dict:
    """Extract correlations, group differences, and summary statistics from data.

    Calls load_and_profile() for data loading, then computes:
    - Pairwise Pearson correlations for numeric columns
    - Group differences for categorical columns with 2-3 groups
    - Per-column summary statistics

    Args:
        filepath: Path to data file (CSV, Excel, JSON).

    Returns:
        Dict with correlations, group_differences, summary, n_rows, n_cols.
    """
    df, _profile = load_and_profile(filepath)

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = []

    # Detect categorical columns: object dtype or int with <= 5 unique values
    for col in df.columns:
        if df[col].dtype == object:
            categorical_cols.append(col)
        elif df[col].dtype in (np.int64, np.int32, int) and df[col].nunique() <= 5:
            categorical_cols.append(col)

    # Pairwise correlations for numeric columns
    correlations = []
    for i in range(len(numeric_cols)):
        for j in range(i + 1, len(numeric_cols)):
            col_a, col_b = numeric_cols[i], numeric_cols[j]
            clean = df[[col_a, col_b]].dropna()
            if len(clean) < 3:
                continue
            r, p = pearsonr(clean[col_a], clean[col_b])
            correlations.append({
                "col_a": col_a,
                "col_b": col_b,
                "r": round(float(r), 4),
                "p_value": round(float(p), 6),
            })

    # Group differences for categorical columns
    group_differences = []
    for cat_col in categorical_cols:
        n_groups = df[cat_col].nunique()
        if n_groups < 2 or n_groups > 3:
            continue

        for num_col in numeric_cols:
            try:
                if n_groups == 2:
                    result = run_statistical_test(
                        df, "ttest_ind",
                        columns={"group_col": cat_col, "value_col": num_col},
                    )
                    effect = result.get("effect_size", 0.0)
                else:
                    result = run_statistical_test(
                        df, "anova",
                        columns={"group_col": cat_col, "value_col": num_col},
                    )
                    effect = result.get("effect_size", 0.0)

                if result["p_value"] < 0.05:
                    group_differences.append({
                        "group_col": cat_col,
                        "numeric_col": num_col,
                        "test": result["test_name"],
                        "p_value": round(result["p_value"], 6),
                        "effect_size": round(float(effect), 4),
                    })
            except (ValueError, KeyError):
                continue

    # Summary statistics
    summary = {}
    for col in numeric_cols:
        summary[col] = {
            "mean": round(float(df[col].mean()), 4),
            "std": round(float(df[col].std()), 4),
            "min": round(float(df[col].min()), 4),
            "max": round(float(df[col].max()), 4),
        }

    return {
        "correlations": correlations,
        "group_differences": group_differences,
        "summary": summary,
        "n_rows": len(df),
        "n_cols": len(df.columns),
    }


# ---------------------------------------------------------------------------
# Hypothesis Validation (HYPO-03, D-09)
# ---------------------------------------------------------------------------

def validate_hypothesis(
    df: pd.DataFrame,
    hypothesis_type: str,
    col_a: str,
    col_b: Optional[str] = None,
    group_col: Optional[str] = None,
    alpha: float = DEFAULT_ALPHA,
    data_file: Optional[str] = None,
) -> dict:
    """Validate a hypothesis using statistical tests from data_ops.

    Delegates to run_statistical_test() (no code duplication per D-09),
    then classifies the result on the evidence spectrum.

    Args:
        df: Input DataFrame.
        hypothesis_type: One of 'group_comparison', 'correlation', 'auto'.
        col_a: Primary column (value column for group comparison, or first var for correlation).
        col_b: Second variable (for correlation).
        group_col: Grouping column (for group comparison).
        alpha: Significance level.
        data_file: Optional path to data file for reproducibility logging.

    Returns:
        Dict with test_used, test_results, evidence, and reasoning.
    """
    # Auto-detect hypothesis type
    if hypothesis_type == "auto":
        if group_col is not None:
            n_groups = df[group_col].nunique()
            if n_groups == 2:
                hypothesis_type = "group_comparison"
            elif n_groups > 2:
                hypothesis_type = "group_comparison"
            else:
                hypothesis_type = "correlation"
        elif col_b is not None:
            hypothesis_type = "correlation"
        else:
            raise ValueError(
                "Cannot auto-detect hypothesis type: provide group_col or col_b"
            )

    # Run the appropriate test
    if hypothesis_type == "group_comparison":
        if group_col is None:
            raise ValueError("group_col required for group_comparison")
        n_groups = df[group_col].nunique()
        test_type = "ttest_ind" if n_groups == 2 else "anova"
        test_results = run_statistical_test(
            df, test_type,
            columns={"group_col": group_col, "value_col": col_a},
            alpha=alpha,
        )
    elif hypothesis_type == "correlation":
        if col_b is None:
            raise ValueError("col_b required for correlation")
        test_results = run_statistical_test(
            df, "pearson",
            columns={"col_a": col_a, "col_b": col_b},
            alpha=alpha,
        )
    else:
        raise ValueError(
            f"Unknown hypothesis_type: {hypothesis_type}. "
            "Supported: group_comparison, correlation, auto"
        )

    # Extract values for evidence classification
    p_value = test_results["p_value"]
    effect_size = test_results.get("effect_size", test_results.get("statistic", 0.0))
    ci = test_results.get("ci_95", (0.0, 0.0))
    ci_lower, ci_upper = ci

    # Classify evidence
    evidence = classify_evidence(p_value, effect_size, ci_lower, ci_upper)

    # Log to reproducibility ledger
    log_operation(
        skill="sci-hypothesis",
        operation="validate_hypothesis",
        params={
            "hypothesis_type": hypothesis_type,
            "col_a": col_a,
            "col_b": col_b,
            "group_col": group_col,
            "alpha": alpha,
            "verdict": evidence["verdict"],
        },
        data_files=[data_file] if data_file else None,
    )

    test_type_used = test_results.get("test_type", "unknown")
    reasoning = (
        f"Used {test_results.get('test_name', test_type_used)} "
        f"to evaluate the hypothesis. {evidence['rationale']}"
    )

    return {
        "test_used": test_type_used,
        "test_results": test_results,
        "evidence": evidence,
        "reasoning": reasoning,
    }


# ---------------------------------------------------------------------------
# Experiment Design (HYPO-02, HYPO-05)
# ---------------------------------------------------------------------------

def design_experiment(
    hypothesis: str,
    effect_size: float,
    test_type: str = "ttest",
    alpha: float = DEFAULT_ALPHA,
    power: float = DEFAULT_POWER,
    k_groups: int = 2,
) -> dict:
    """Generate an experiment design with power analysis.

    Python provides the structure and sample size calculations.
    Variables, controls, analysis_plan, and limitations are placeholder
    strings that Claude fills in at the LLM level.

    Args:
        hypothesis: Hypothesis statement.
        effect_size: Expected effect size.
        test_type: One of 'ttest', 'anova', 'chisq' (default 'ttest').
        alpha: Significance level (default 0.05).
        power: Desired statistical power (default 0.80).
        k_groups: Number of groups (for ANOVA, default 2).

    Returns:
        Dict with hypothesis, variables, design_type, sample_size,
        controls, analysis_plan, limitations.
    """
    # Run appropriate power analysis
    if test_type == "ttest":
        sample_size = ttest_power_analysis(
            effect_size=effect_size, alpha=alpha, power=power,
        )
        design_type = "Two-group comparison (independent samples)"
        analysis = f"Independent samples t-test with alpha={alpha}"
    elif test_type == "anova":
        sample_size = anova_power_analysis(
            effect_size=effect_size, k_groups=k_groups,
            alpha=alpha, power=power,
        )
        design_type = f"Multi-group comparison ({k_groups} groups)"
        analysis = f"One-way ANOVA with alpha={alpha}, followed by post-hoc tests if significant"
    elif test_type == "chisq":
        sample_size = chisq_power_analysis(
            effect_size=effect_size, df=k_groups - 1,
            alpha=alpha, power=power,
        )
        design_type = "Categorical association test"
        analysis = f"Chi-square test of independence with alpha={alpha}"
    else:
        raise ValueError(
            f"Unknown test_type: {test_type}. Supported: ttest, anova, chisq"
        )

    return {
        "hypothesis": hypothesis,
        "variables": {
            "independent": "[To be specified by researcher]",
            "dependent": "[To be specified by researcher]",
            "controls": ["[To be specified by researcher]"],
        },
        "design_type": design_type,
        "sample_size": sample_size,
        "controls": [
            "Randomization of participants to groups",
            "Control group included",
        ],
        "analysis_plan": analysis,
        "limitations": [
            "Effect size estimate may differ from observed",
            "Power analysis assumes equal variances",
        ],
    }


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def generate_hypothesis_report(results: dict) -> str:
    """Generate a structured markdown report from hypothesis validation results.

    Args:
        results: Dict from validate_hypothesis() or similar structure.

    Returns:
        Markdown string with Hypothesis, Data Patterns, Evidence, Verdict sections.
    """
    lines = []

    # Hypothesis
    lines.append("## Hypothesis\n")
    lines.append(results.get("hypothesis", "[No hypothesis specified]"))
    lines.append("")

    # Data Patterns
    lines.append("## Data Patterns\n")
    test_results = results.get("test_results", {})
    if test_results:
        stat = test_results.get("statistic")
        if stat is not None:
            lines.append(f"- **Test statistic:** {stat:.4f}")
        p = test_results.get("p_value")
        if p is not None:
            lines.append(f"- **p-value:** {p:.6f}")
    lines.append("")

    # Evidence
    evidence = results.get("evidence", {})
    lines.append("## Evidence\n")
    lines.append(f"- **p-value:** {evidence.get('p_value', 'N/A')}")
    lines.append(f"- **Effect size:** {evidence.get('effect_size', 'N/A')}")
    ci = evidence.get("ci_95", ("N/A", "N/A"))
    lines.append(f"- **95% CI:** ({ci[0]}, {ci[1]})")
    lines.append(f"- **Rationale:** {evidence.get('rationale', 'N/A')}")
    lines.append("")

    # Verdict
    lines.append("## Verdict\n")
    lines.append(f"**{evidence.get('verdict', 'N/A')}**")
    lines.append("")

    return "\n".join(lines)


def generate_experiment_report(design: dict) -> str:
    """Generate a structured markdown report from experiment design.

    Args:
        design: Dict from design_experiment() or similar structure.

    Returns:
        Markdown string with Hypothesis, Variables, Design Type, Sample Size,
        Controls, Analysis Plan, Limitations sections.
    """
    lines = []

    # Hypothesis
    lines.append("## Hypothesis\n")
    lines.append(design.get("hypothesis", "[No hypothesis specified]"))
    lines.append("")

    # Variables
    variables = design.get("variables", {})
    lines.append("## Variables\n")
    lines.append(f"- **Independent:** {variables.get('independent', 'N/A')}")
    lines.append(f"- **Dependent:** {variables.get('dependent', 'N/A')}")
    controls_list = variables.get("controls", [])
    if controls_list:
        lines.append(f"- **Control variables:** {', '.join(controls_list)}")
    lines.append("")

    # Design Type
    lines.append("## Design Type\n")
    lines.append(design.get("design_type", "N/A"))
    lines.append("")

    # Sample Size
    sample_size = design.get("sample_size", {})
    lines.append("## Sample Size\n")
    if "n1" in sample_size:
        lines.append(f"- **Group 1:** {sample_size['n1']}")
        lines.append(f"- **Group 2:** {sample_size['n2']}")
        lines.append(f"- **Total:** {sample_size['total_n']}")
    elif "n_per_group" in sample_size:
        lines.append(f"- **Per group:** {sample_size['n_per_group']}")
        lines.append(f"- **Total:** {sample_size['total_n']}")
    elif "total_n" in sample_size:
        lines.append(f"- **Total:** {sample_size['total_n']}")
    lines.append(f"- **Actual power:** {sample_size.get('actual_power', 'N/A')}")
    lines.append("")

    # Sensitivity table
    sensitivity = sample_size.get("sensitivity_table", [])
    if sensitivity:
        lines.append("### Sensitivity Table\n")
        lines.append("| Effect Size | Power | N per Group |")
        lines.append("|-------------|-------|-------------|")
        for entry in sensitivity:
            n_col = entry.get("n_per_group", entry.get("total_n", "N/A"))
            lines.append(
                f"| {entry['effect_size']:.2f} | {entry['power']:.2f} | {n_col} |"
            )
        lines.append("")

    # Controls
    controls = design.get("controls", [])
    lines.append("## Controls\n")
    for c in controls:
        lines.append(f"- {c}")
    lines.append("")

    # Analysis Plan
    lines.append("## Analysis Plan\n")
    lines.append(design.get("analysis_plan", "N/A"))
    lines.append("")

    # Limitations
    limitations = design.get("limitations", [])
    lines.append("## Limitations\n")
    for lim in limitations:
        lines.append(f"- {lim}")
    lines.append("")

    return "\n".join(lines)
