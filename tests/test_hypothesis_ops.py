"""Tests for sci-hypothesis hypothesis_ops module.

Covers pattern analysis (HYPO-01), power analysis (HYPO-05),
evidence spectrum classification (HYPO-04/HYPO-03), hypothesis
validation (HYPO-03), experiment design (HYPO-02/HYPO-05),
and report generation.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

# Add scripts dir to path for hypothesis_ops import
SCRIPTS_DIR = str(
    Path(__file__).resolve().parent.parent
    / ".claude" / "skills" / "sci-hypothesis" / "scripts"
)
sys.path.insert(0, SCRIPTS_DIR)

from hypothesis_ops import (
    analyze_patterns,
    anova_power_analysis,
    chisq_power_analysis,
    classify_evidence,
    design_experiment,
    generate_experiment_report,
    generate_hypothesis_report,
    ttest_power_analysis,
    validate_hypothesis,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_CSV = str(FIXTURES_DIR / "hypothesis_sample.csv")


# ---------------------------------------------------------------------------
# Pattern Analysis Tests (HYPO-01)
# ---------------------------------------------------------------------------

class TestAnalyzePatterns:
    def test_returns_correlations(self, tmp_repro_dir):
        result = analyze_patterns(FIXTURE_CSV)
        assert "correlations" in result
        # expression_level and response_score should be correlated (r > 0.3)
        strong_corrs = [
            c for c in result["correlations"] if abs(c["r"]) > 0.3
        ]
        assert len(strong_corrs) > 0

    def test_returns_group_differences(self, tmp_repro_dir):
        result = analyze_patterns(FIXTURE_CSV)
        assert "group_differences" in result
        # Should detect expression_level differs between treatment/control
        expr_diffs = [
            d for d in result["group_differences"]
            if d["numeric_col"] == "expression_level"
        ]
        assert len(expr_diffs) > 0
        assert expr_diffs[0]["p_value"] < 0.05

    def test_returns_summary_stats(self, tmp_repro_dir):
        result = analyze_patterns(FIXTURE_CSV)
        assert "summary" in result
        # Summary should have per-column means
        summary = result["summary"]
        assert "expression_level" in summary
        assert "mean" in summary["expression_level"]

    def test_handles_missing_groups_column(self, tmp_repro_dir, tmp_path):
        # Create a CSV with only numeric columns (no categorical)
        df = pd.DataFrame({
            "x": np.random.randn(30),
            "y": np.random.randn(30),
            "z": np.random.randn(30),
        })
        csv_path = str(tmp_path / "numeric_only.csv")
        df.to_csv(csv_path, index=False)

        result = analyze_patterns(csv_path)
        assert "correlations" in result
        assert result["group_differences"] == []


# ---------------------------------------------------------------------------
# Power Analysis Tests (HYPO-05)
# ---------------------------------------------------------------------------

class TestPowerAnalysis:
    def test_ttest_small_effect(self):
        result = ttest_power_analysis(effect_size=0.2)
        # Expected n_per_group ~ 393 (within 5%)
        assert abs(result["n1"] - 393) / 393 < 0.05

    def test_ttest_medium_effect(self):
        result = ttest_power_analysis(effect_size=0.5)
        # Expected n_per_group ~ 63 (within 5%)
        assert abs(result["n1"] - 63) / 63 < 0.05

    def test_ttest_large_effect(self):
        result = ttest_power_analysis(effect_size=0.8)
        # Expected n_per_group ~ 25 (within 5%)
        assert abs(result["n1"] - 25) / 25 < 0.05

    def test_sensitivity_table_present(self):
        result = ttest_power_analysis(effect_size=0.5)
        assert "sensitivity_table" in result
        table = result["sensitivity_table"]
        assert isinstance(table, list)
        assert len(table) > 0
        entry = table[0]
        assert "effect_size" in entry
        assert "power" in entry
        assert "n_per_group" in entry

    def test_anova_power(self):
        result = anova_power_analysis(effect_size=0.25, k_groups=3)
        assert result["total_n"] > 0
        assert result["actual_power"] >= 0.80

    def test_chisq_power(self):
        result = chisq_power_analysis(effect_size=0.3, df=2)
        assert result["total_n"] > 0


# ---------------------------------------------------------------------------
# Evidence Spectrum Tests (HYPO-04, HYPO-03)
# ---------------------------------------------------------------------------

class TestEvidenceSpectrum:
    def test_strong_support(self):
        result = classify_evidence(
            p_value=0.001, effect_size=0.8,
            ci_lower=0.3, ci_upper=1.3,
        )
        assert result["verdict"] == "Strong Support"

    def test_moderate_support(self):
        result = classify_evidence(
            p_value=0.03, effect_size=0.4,
            ci_lower=0.1, ci_upper=0.7,
        )
        assert result["verdict"] == "Moderate Support"

    def test_inconclusive(self):
        result = classify_evidence(
            p_value=0.08, effect_size=0.3,
            ci_lower=-0.1, ci_upper=0.7,
        )
        assert result["verdict"] == "Inconclusive"

    def test_moderate_against(self):
        result = classify_evidence(
            p_value=0.5, effect_size=0.05,
            ci_lower=-0.2, ci_upper=0.3,
        )
        assert result["verdict"] == "Moderate Against"

    def test_strong_against(self):
        result = classify_evidence(
            p_value=0.8, effect_size=0.02,
            ci_lower=-0.15, ci_upper=0.19,
        )
        assert result["verdict"] == "Strong Against"

    def test_returns_rationale(self):
        result = classify_evidence(
            p_value=0.001, effect_size=0.8,
            ci_lower=0.3, ci_upper=1.3,
        )
        assert "rationale" in result
        assert isinstance(result["rationale"], str)
        assert len(result["rationale"]) > 0

    def test_returns_all_fields(self):
        result = classify_evidence(
            p_value=0.03, effect_size=0.4,
            ci_lower=0.1, ci_upper=0.7,
        )
        for key in ("verdict", "p_value", "effect_size", "ci_95", "rationale"):
            assert key in result


# ---------------------------------------------------------------------------
# Hypothesis Validation Tests (HYPO-03)
# ---------------------------------------------------------------------------

class TestValidateHypothesis:
    @pytest.fixture
    def sample_df(self):
        return pd.read_csv(FIXTURE_CSV)

    def test_runs_ttest_on_groups(self, sample_df, tmp_repro_dir):
        result = validate_hypothesis(
            sample_df,
            hypothesis_type="group_comparison",
            col_a="expression_level",
            group_col="group",
        )
        assert "evidence" in result
        assert result["evidence"]["verdict"] in (
            "Strong Support", "Moderate Support", "Inconclusive",
            "Moderate Against", "Strong Against",
        )

    def test_runs_correlation(self, sample_df, tmp_repro_dir):
        result = validate_hypothesis(
            sample_df,
            hypothesis_type="correlation",
            col_a="treatment_days",
            col_b="expression_level",
        )
        assert "evidence" in result
        assert "test_results" in result

    def test_logs_to_repro(self, sample_df, tmp_repro_dir):
        with patch("hypothesis_ops.log_operation") as mock_log:
            validate_hypothesis(
                sample_df,
                hypothesis_type="group_comparison",
                col_a="expression_level",
                group_col="group",
            )
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args
            assert call_kwargs[1]["skill"] == "sci-hypothesis" or call_kwargs[0][0] == "sci-hypothesis"

    def test_auto_selects_test(self, sample_df, tmp_repro_dir):
        result = validate_hypothesis(
            sample_df,
            hypothesis_type="auto",
            col_a="expression_level",
            group_col="group",
        )
        assert result["test_used"] in ("ttest_ind", "anova")


# ---------------------------------------------------------------------------
# Experiment Design Tests (HYPO-02, HYPO-05)
# ---------------------------------------------------------------------------

class TestDesignExperiment:
    def test_returns_required_sections(self):
        result = design_experiment(
            hypothesis="Treatment increases expression",
            effect_size=0.5,
        )
        for key in (
            "hypothesis", "variables", "design_type",
            "sample_size", "controls", "analysis_plan", "limitations",
        ):
            assert key in result

    def test_sample_size_uses_power_analysis(self):
        result = design_experiment(
            hypothesis="Treatment increases expression",
            effect_size=0.5,
            test_type="ttest",
        )
        ss = result["sample_size"]
        assert "n1" in ss or "n_per_group" in ss
        assert "actual_power" in ss

    def test_includes_sensitivity_table(self):
        result = design_experiment(
            hypothesis="Treatment increases expression",
            effect_size=0.5,
            test_type="ttest",
        )
        assert "sensitivity_table" in result["sample_size"]

    def test_default_power_80(self):
        result = design_experiment(
            hypothesis="Treatment increases expression",
            effect_size=0.5,
        )
        assert result["sample_size"]["actual_power"] >= 0.79


# ---------------------------------------------------------------------------
# Report Generation Tests
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_hypothesis_report_has_sections(self):
        results = {
            "test_used": "ttest_ind",
            "test_results": {"statistic": 3.5, "p_value": 0.001},
            "evidence": {
                "verdict": "Strong Support",
                "p_value": 0.001,
                "effect_size": 0.8,
                "ci_95": (0.3, 1.3),
                "rationale": "Strong statistical evidence.",
            },
            "hypothesis": "Treatment increases expression",
        }
        report = generate_hypothesis_report(results)
        assert "## Hypothesis" in report
        assert "## Evidence" in report
        assert "## Verdict" in report

    def test_experiment_report_has_sections(self):
        design = {
            "hypothesis": "Treatment increases expression",
            "variables": {
                "independent": "treatment",
                "dependent": "expression_level",
                "controls": ["age", "batch"],
            },
            "design_type": "Randomized Controlled Trial",
            "sample_size": {
                "n1": 63, "n2": 63, "total_n": 126,
                "actual_power": 0.80,
                "sensitivity_table": [
                    {"effect_size": 0.5, "power": 0.80, "n_per_group": 63},
                ],
            },
            "controls": ["Randomization", "Blinding"],
            "analysis_plan": "Independent t-test with alpha=0.05",
            "limitations": ["Single-center study"],
        }
        report = generate_experiment_report(design)
        assert "## Variables" in report
        assert "## Sample Size" in report
        assert "## Controls" in report
        assert "## Analysis Plan" in report
