"""Tests for sci-data-analysis data_ops module.

Covers data loading (CSV/Excel/JSON/unsupported), statistical tests
(t-test/ANOVA/chi-square/Pearson/Spearman), regression (linear/logistic),
data cleaning (drop/fill/outliers/z-score/min-max), report generation,
and reproducibility logging.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

# Add scripts dir to path for data_ops import
SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / ".claude" / "skills" / "sci-data-analysis" / "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from data_ops import (
    clean_data,
    generate_report,
    load_and_profile,
    run_regression,
    run_statistical_test,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# Data Loading Tests (DATA-01)
# ---------------------------------------------------------------------------

class TestLoadCSV:
    def test_load_csv(self, tmp_repro_dir):
        df, profile = load_and_profile(str(FIXTURES_DIR / "sample_data.csv"))
        assert df.shape == (20, 6)
        assert "20 rows x 6 columns" in profile

    def test_profile_contains_stats(self, tmp_repro_dir):
        df, profile = load_and_profile(str(FIXTURES_DIR / "sample_data.csv"))
        assert "Summary Statistics" in profile
        assert "group" in profile
        assert "value1" in profile


class TestLoadJSON:
    def test_load_json(self, tmp_repro_dir):
        df, profile = load_and_profile(str(FIXTURES_DIR / "sample_data.json"))
        assert df.shape == (20, 6)


class TestLoadExcel:
    def test_load_excel(self, tmp_path, tmp_repro_dir):
        # Create a temp Excel file from the CSV fixture
        csv_df = pd.read_csv(FIXTURES_DIR / "sample_data.csv")
        xlsx_path = tmp_path / "test.xlsx"
        csv_df.to_excel(xlsx_path, index=False)
        df, profile = load_and_profile(str(xlsx_path))
        assert df.shape == csv_df.shape


class TestLoadUnsupported:
    def test_load_unsupported(self, tmp_path, tmp_repro_dir):
        txt_file = tmp_path / "data.txt"
        txt_file.write_text("some text")
        with pytest.raises(ValueError, match="Unsupported format"):
            load_and_profile(str(txt_file))


# ---------------------------------------------------------------------------
# Statistical Test Tests (DATA-02)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df():
    return pd.read_csv(FIXTURES_DIR / "sample_data.csv")


class TestTTestIndependent:
    def test_ttest_independent(self, sample_df, tmp_repro_dir):
        result = run_statistical_test(
            sample_df, "ttest_ind",
            columns={"group_col": "group", "value_col": "value1"},
        )
        assert "test_name" in result
        assert "assumptions" in result
        assert "statistic" in result
        assert "p_value" in result
        assert "effect_size" in result
        assert "significant" in result
        # Groups A (~10) vs B (~15) should be significant
        assert result["significant"] is True

    def test_ttest_assumptions(self, sample_df, tmp_repro_dir):
        result = run_statistical_test(
            sample_df, "ttest_ind",
            columns={"group_col": "group", "value_col": "value1"},
        )
        assumptions = result["assumptions"]
        assert "normality_a" in assumptions
        assert "normality_b" in assumptions
        assert "homogeneity" in assumptions
        for key in ("normality_a", "normality_b", "homogeneity"):
            a = assumptions[key]
            assert "statistic" in a
            assert "p_value" in a
            assert "passed" in a


class TestANOVA:
    def test_anova(self, sample_df, tmp_repro_dir):
        result = run_statistical_test(
            sample_df, "anova",
            columns={"group_col": "category", "value_col": "value1"},
        )
        assert "statistic" in result
        assert "p_value" in result
        assert result["test_name"] == "One-way ANOVA"


class TestChiSquare:
    def test_chi_square(self, sample_df, tmp_repro_dir):
        result = run_statistical_test(
            sample_df, "chi_square",
            columns={"col_a": "group", "col_b": "category"},
        )
        assert "statistic" in result
        assert "p_value" in result
        assert "cramers_v" in result


class TestPearson:
    def test_pearson(self, sample_df, tmp_repro_dir):
        result = run_statistical_test(
            sample_df, "pearson",
            columns={"col_a": "value1", "col_b": "value2"},
        )
        # Correlation should be strong positive (~0.99 for our fixture data)
        assert result["statistic"] > 0.7
        assert result["p_value"] < 0.05


class TestSpearman:
    def test_spearman(self, sample_df, tmp_repro_dir):
        result = run_statistical_test(
            sample_df, "spearman",
            columns={"col_a": "value1", "col_b": "value2"},
        )
        assert "statistic" in result
        assert "p_value" in result


# ---------------------------------------------------------------------------
# Regression Tests (DATA-02, D-08)
# ---------------------------------------------------------------------------

class TestLinearRegression:
    def test_linear_regression(self, sample_df, tmp_repro_dir):
        result = run_regression(sample_df, ["value1"], "value2", reg_type="linear")
        assert result["r_squared"] > 0.3
        assert "slope" in result
        assert "intercept" in result
        assert "residuals" in result
        assert len(result["residuals"]) == len(sample_df)


class TestLogisticRegression:
    def test_logistic_regression(self, tmp_repro_dir):
        # Create a clear binary classification dataset
        df = pd.DataFrame({
            "x": [8, 9, 10, 11, 7, 6, 14, 15, 16, 17, 18, 19],
            "y": [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
        })
        result = run_regression(df, ["x"], "y", reg_type="logistic")
        assert "coefficients" in result
        assert "odds_ratios" in result
        assert len(result["coefficients"]) == len(result["odds_ratios"])


# ---------------------------------------------------------------------------
# Data Cleaning Tests (DATA-03)
# ---------------------------------------------------------------------------

class TestCleanDropMissing:
    def test_clean_drop_missing(self, sample_df, tmp_repro_dir):
        original_rows = len(sample_df)
        cleaned, comparison = clean_data(
            sample_df,
            [{"type": "drop_missing", "columns": ["missing_col"]}],
        )
        assert len(cleaned) < original_rows
        assert cleaned["missing_col"].isnull().sum() == 0


class TestCleanFillMean:
    def test_clean_fill_mean(self, sample_df, tmp_repro_dir):
        cleaned, comparison = clean_data(
            sample_df,
            [{"type": "fill_missing", "columns": ["missing_col"], "method": "mean"}],
        )
        assert cleaned["missing_col"].isnull().sum() == 0


class TestCleanRemoveOutliers:
    def test_clean_remove_outliers(self, sample_df, tmp_repro_dir):
        cleaned, comparison = clean_data(
            sample_df,
            [{"type": "remove_outliers", "columns": ["value1"], "method": "iqr", "factor": 1.5}],
        )
        assert "rows before" in comparison
        assert "rows after" in comparison


class TestCleanNormalizeZscore:
    def test_clean_normalize_zscore(self, sample_df, tmp_repro_dir):
        cleaned, comparison = clean_data(
            sample_df,
            [{"type": "normalize", "columns": ["value1"], "method": "zscore"}],
        )
        # Z-score: mean ~0, std ~1
        assert abs(cleaned["value1"].mean()) < 0.01
        assert abs(cleaned["value1"].std() - 1.0) < 0.1


class TestCleanNormalizeMinmax:
    def test_clean_normalize_minmax(self, sample_df, tmp_repro_dir):
        cleaned, comparison = clean_data(
            sample_df,
            [{"type": "normalize", "columns": ["value1"], "method": "minmax"}],
        )
        assert abs(cleaned["value1"].min() - 0.0) < 0.001
        assert abs(cleaned["value1"].max() - 1.0) < 0.001


# ---------------------------------------------------------------------------
# Report Generation Tests (DATA-04, D-07)
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_generate_report(self, sample_df, tmp_repro_dir):
        result = run_statistical_test(
            sample_df, "ttest_ind",
            columns={"group_col": "group", "value_col": "value1"},
        )
        report = generate_report(result, "ttest_ind")
        assert "## Test Selected" in report
        assert "## Assumptions Check" in report
        assert "## Results" in report
        assert "## Interpretation" in report


# ---------------------------------------------------------------------------
# Reproducibility Logging Tests (DATA-05)
# ---------------------------------------------------------------------------

class TestReproLogging:
    def test_repro_logging(self, tmp_repro_dir):
        ledger_path = tmp_repro_dir / "ledger.jsonl"
        load_and_profile(str(FIXTURES_DIR / "sample_data.csv"))
        assert ledger_path.exists()
        entries = [json.loads(line) for line in ledger_path.read_text().strip().split("\n")]
        assert any(e["skill"] == "sci-data-analysis" for e in entries)
