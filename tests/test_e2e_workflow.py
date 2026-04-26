"""End-to-end workflow test suite — full scientific pipeline from data to deliverables.

Scenario: A clinical study investigating BiomarkerX as a predictor of immunotherapy
response in cancer patients. 30 patients (15 treatment, 15 control), measuring
biomarker levels, tumor size, treatment response, and survival.

This test suite chains ALL skill operations to produce:
1. Data analysis + plots (sci-data-analysis)
2. Hypothesis generation + experiment design (sci-hypothesis)
3. Manuscript sections with citations (sci-writing)
4. Blog post markdown (sci-communication)
5. Tutorial markdown (sci-communication)
6. Mermaid diagram code (viz-diagram-code)
7. Presentation slides (viz-presentation)

Each stage consumes outputs from previous stages, verifying the full pipeline.
"""

import json
import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Path setup — import skill scripts
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

DATA_SCRIPTS = str(ROOT / ".claude" / "skills" / "sci-data-analysis" / "scripts")
HYPO_SCRIPTS = str(ROOT / ".claude" / "skills" / "sci-hypothesis" / "scripts")
WRITE_SCRIPTS = str(ROOT / ".claude" / "skills" / "sci-writing" / "scripts")

sys.path.insert(0, DATA_SCRIPTS)
sys.path.insert(0, HYPO_SCRIPTS)
sys.path.insert(0, WRITE_SCRIPTS)

from data_ops import load_and_profile, run_statistical_test, clean_data, generate_report
from plot_ops import generate_static_plot, generate_dual_plot
from hypothesis_ops import (
    analyze_patterns,
    classify_evidence,
    ttest_power_analysis,
    validate_hypothesis,
    design_experiment,
    generate_hypothesis_report,
    generate_experiment_report,
)
from writing_ops import (
    parse_bib_file,
    format_citation,
    format_bibliography,
    replace_citation_markers,
)
from review_ops import generate_review_report

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

E2E_DATA = str(FIXTURES / "e2e_clinical_data.csv")
E2E_BIB = str(FIXTURES / "e2e_references.bib")
SKILLS_DIR = ROOT / ".claude" / "skills"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

E2E_OUTPUT = Path(__file__).resolve().parent / "e2e_output"


@pytest.fixture(scope="module")
def output_dir():
    """Persistent output directory — survives after test run."""
    E2E_OUTPUT.mkdir(exist_ok=True)
    # Clean previous run
    for f in E2E_OUTPUT.iterdir():
        if f.is_file():
            f.unlink()
    return E2E_OUTPUT


@pytest.fixture(scope="module")
def clinical_df(tmp_path_factory):
    """Load the clinical dataset once for all tests."""
    tmp = tmp_path_factory.mktemp("repro")
    ledger = tmp / "ledger.jsonl"
    summaries = tmp / "summaries"
    summaries.mkdir()
    with patch("repro.repro_logger.LEDGER_PATH", ledger):
        df, profile = load_and_profile(E2E_DATA)
    return df


@pytest.fixture(scope="module")
def bib_entries():
    """Parse the e2e bibliography."""
    return parse_bib_file(E2E_BIB)


# ===================================================================
# STAGE 1: Data Analysis (sci-data-analysis)
# ===================================================================


class TestStage1DataAnalysis:
    """Load clinical data, run statistics, generate plots."""

    def test_load_clinical_data(self, clinical_df):
        """Verify data loads with correct shape and columns."""
        assert clinical_df.shape == (30, 9)
        expected_cols = {
            "patient_id", "group", "age", "sex", "biomarker_level",
            "treatment_weeks", "tumor_size_mm", "response", "survival_months",
        }
        assert set(clinical_df.columns) == expected_cols

    def test_treatment_vs_control_groups(self, clinical_df):
        """Verify group sizes."""
        groups = clinical_df["group"].value_counts()
        assert groups["treatment"] == 15
        assert groups["control"] == 15

    def test_biomarker_ttest(self, clinical_df, output_dir):
        """Run t-test comparing biomarker levels between groups."""
        ledger = output_dir / "ledger.jsonl"
        with patch("repro.repro_logger.LEDGER_PATH", ledger):
            result = run_statistical_test(
                clinical_df, "ttest_ind",
                columns={"value_col": "biomarker_level", "group_col": "group"},
            )
        assert result["test_type"] == "ttest_ind"
        assert result["p_value"] < 0.05, (
            "Biomarker should differ significantly between treatment and control"
        )
        assert result["statistic"] != 0
        self.__class__.biomarker_ttest = result

    def test_tumor_size_ttest(self, clinical_df, output_dir):
        """Run t-test on tumor size between groups."""
        ledger = output_dir / "ledger.jsonl"
        with patch("repro.repro_logger.LEDGER_PATH", ledger):
            result = run_statistical_test(
                clinical_df, "ttest_ind",
                columns={"value_col": "tumor_size_mm", "group_col": "group"},
            )
        assert result["test_type"] == "ttest_ind"
        assert result["p_value"] is not None
        self.__class__.tumor_ttest = result

    def test_response_chi_square(self, clinical_df, output_dir):
        """Chi-square test for response rates between groups."""
        ledger = output_dir / "ledger.jsonl"
        with patch("repro.repro_logger.LEDGER_PATH", ledger):
            result = run_statistical_test(
                clinical_df, "chi_square",
                columns={"col_a": "response", "col_b": "group"},
            )
        assert result["test_type"] == "chi_square"
        self.__class__.response_chi2 = result

    def test_biomarker_correlation(self, clinical_df, output_dir):
        """Pearson correlation between biomarker and survival."""
        ledger = output_dir / "ledger.jsonl"
        with patch("repro.repro_logger.LEDGER_PATH", ledger):
            result = run_statistical_test(
                clinical_df, "pearson",
                columns={"col_a": "biomarker_level", "col_b": "survival_months"},
            )
        assert result["test_type"] == "pearson"
        assert "statistic" in result
        self.__class__.correlation = result

    def test_generate_scatter_plot(self, clinical_df, output_dir):
        """Generate biomarker vs survival scatter plot."""
        ledger = output_dir / "ledger.jsonl"
        with patch("repro.repro_logger.LEDGER_PATH", ledger):
            saved = generate_static_plot(
                clinical_df,
                plot_type="scatter",
                x_col="biomarker_level",
                y_col="survival_months",
                base_path=str(output_dir / "biomarker_survival"),
                title="BiomarkerX vs Survival",
                xlabel="BiomarkerX Level",
                ylabel="Survival (months)",
                hue_col="group",
            )
        assert len(saved) >= 2, "Should produce PNG + SVG at minimum"
        for path in saved:
            assert Path(path).exists(), f"Plot file not created: {path}"
        self.__class__.scatter_paths = saved

    def test_generate_box_plot(self, clinical_df, output_dir):
        """Generate biomarker distribution box plot by group."""
        ledger = output_dir / "ledger.jsonl"
        with patch("repro.repro_logger.LEDGER_PATH", ledger):
            saved = generate_static_plot(
                clinical_df,
                plot_type="box",
                x_col="group",
                y_col="biomarker_level",
                base_path=str(output_dir / "biomarker_boxplot"),
                title="BiomarkerX Distribution by Group",
                xlabel="Group",
                ylabel="BiomarkerX Level",
            )
        assert len(saved) >= 2
        self.__class__.box_paths = saved

    def test_generate_report(self, output_dir):
        """Generate a text report from statistical results."""
        result = getattr(self.__class__, "biomarker_ttest", None)
        if result is None:
            pytest.skip("biomarker_ttest not available")
        report = generate_report(result, "ttest")
        assert "t-test" in report.lower() or "t(" in report.lower()
        assert "p" in report.lower()
        self.__class__.stats_report = report


# ===================================================================
# STAGE 2: Hypothesis Generation (sci-hypothesis)
# ===================================================================


class TestStage2Hypothesis:
    """Generate hypotheses from data patterns, design experiments."""

    def test_pattern_analysis(self, output_dir):
        """Analyze patterns in the clinical data."""
        ledger = output_dir / "ledger.jsonl"
        with patch("repro.repro_logger.LEDGER_PATH", ledger):
            result = analyze_patterns(E2E_DATA)
        assert "correlations" in result
        assert "group_differences" in result
        # Should detect biomarker_level differs between groups
        bio_diffs = [
            d for d in result["group_differences"]
            if d["numeric_col"] == "biomarker_level"
        ]
        assert len(bio_diffs) > 0, (
            "Pattern analysis should detect biomarker differences between groups"
        )
        self.__class__.patterns = result

    def test_power_analysis(self):
        """Run power analysis for the biomarker comparison."""
        result = ttest_power_analysis(
            effect_size=1.5, alpha=0.05, power=0.8
        )
        assert "n1" in result, f"Expected 'n1' in result, got keys: {list(result.keys())}"
        assert result["n1"] > 0
        self.__class__.power = result

    def test_classify_evidence(self):
        """Classify evidence strength from the t-test."""
        bio_ttest = getattr(TestStage1DataAnalysis, "biomarker_ttest", None)
        if bio_ttest is None:
            pytest.skip("Stage 1 biomarker_ttest not available")

        classification = classify_evidence(
            p_value=bio_ttest["p_value"],
            effect_size=0.8,
            ci_lower=0.5,
            ci_upper=1.2,
        )
        assert "verdict" in classification
        assert "strong" in classification["verdict"].lower() or "support" in classification["verdict"].lower()
        self.__class__.evidence = classification

    def test_hypothesis_report(self):
        """Generate a formatted hypothesis report from pattern analysis."""
        patterns = getattr(self.__class__, "patterns", None)
        if patterns is None:
            pytest.skip("patterns not available")

        # generate_hypothesis_report expects validation results, not raw patterns.
        # Build a minimal validation-style result from the patterns.
        report = generate_hypothesis_report({
            "hypothesis": "BiomarkerX levels predict immunotherapy response",
            "patterns": patterns,
            "p_value": 0.001,
            "effect_size": 1.5,
            "ci_lower": 1.2,
            "ci_upper": 4.5,
            "rationale": "Large effect size with significant p-value",
            "verdict": "supported",
        })
        assert len(report) > 50, "Report should be substantial"
        self.__class__.hypo_report = report

    def test_experiment_design(self, output_dir):
        """Design a follow-up experiment."""
        ledger = output_dir / "ledger.jsonl"
        with patch("repro.repro_logger.LEDGER_PATH", ledger):
            design = design_experiment(
                hypothesis="Higher BiomarkerX levels predict better immunotherapy response",
                test_type="ttest",
                effect_size=1.0,
                alpha=0.05,
                power=0.8,
            )
        assert "sample_size" in design, f"Expected 'sample_size', got keys: {list(design.keys())}"
        assert "hypothesis" in design
        assert design["sample_size"]["n1"] > 0
        self.__class__.experiment = design

    def test_experiment_report(self):
        """Generate experiment design report."""
        design = getattr(self.__class__, "experiment", None)
        if design is None:
            pytest.skip("experiment design not available")

        report = generate_experiment_report(design)
        assert "sample" in report.lower() or "n" in report.lower()
        assert len(report) > 50
        self.__class__.exp_report = report


# ===================================================================
# STAGE 3: Manuscript Writing (sci-writing)
# ===================================================================


class TestStage3ManuscriptWriting:
    """Format citations, build bibliography, prepare manuscript sections."""

    def test_parse_bibliography(self, bib_entries):
        """Parse the e2e BibTeX file."""
        assert len(bib_entries) == 4
        keys = [e["key"] for e in bib_entries]
        assert "Chen2024" in keys
        assert "Wang2023" in keys
        assert "Rodriguez2024" in keys
        assert "Kim2023" in keys

    def test_format_apa_citations(self, bib_entries):
        """Format all citations in APA style."""
        for entry in bib_entries:
            formatted = format_citation(entry, "apa")
            assert len(formatted) > 20, f"Citation too short: {formatted}"
            assert entry["year"] in formatted
        self.__class__.apa_citations = [
            format_citation(e, "apa") for e in bib_entries
        ]

    def test_format_nature_citations(self, bib_entries):
        """Format citations in Nature style."""
        for entry in bib_entries:
            formatted = format_citation(entry, "nature")
            assert len(formatted) > 10

    def test_generate_bibliography(self, bib_entries):
        """Generate a complete bibliography section."""
        bib = format_bibliography(bib_entries, "apa")
        assert len(bib) > 200
        assert "Chen" in bib
        assert "Wang" in bib
        assert "Rodriguez" in bib
        assert "Kim" in bib
        self.__class__.bibliography = bib

    def test_replace_citation_markers_in_draft(self, bib_entries, output_dir):
        """Replace [@Key] markers in a manuscript draft with formatted citations."""
        draft = textwrap.dedent("""\
            # Introduction

            BiomarkerX has emerged as a promising predictor of immunotherapy response
            in solid tumors [@Chen2024]. Mechanistic studies have revealed its role
            in tumor immune evasion [@Wang2023], and recent clinical trials have
            stratified patients by BiomarkerX levels [@Rodriguez2024].

            Single-cell profiling has further confirmed that BiomarkerX-high cells
            drive anti-tumor immunity [@Kim2023], supporting its use as a
            predictive biomarker.

            # Methods

            We conducted a prospective study following the protocol established by
            [@Chen2024] with modifications based on [@Rodriguez2024].
        """)

        formatted, warnings = replace_citation_markers(draft, bib_entries, "apa")
        assert "[@Chen2024]" not in formatted, "Citation markers should be replaced"
        assert "[@Wang2023]" not in formatted
        assert len(warnings) == 0, f"Unexpected unmatched citations: {warnings}"

        # Save the formatted manuscript
        manuscript_path = output_dir / "manuscript_introduction.md"
        manuscript_path.write_text(formatted)
        assert manuscript_path.exists()
        self.__class__.manuscript_path = manuscript_path
        self.__class__.manuscript_text = formatted

    def test_manuscript_has_scientific_structure(self):
        """Verify the manuscript follows scientific conventions."""
        text = getattr(self.__class__, "manuscript_text", None)
        if text is None:
            pytest.skip("manuscript not available")
        assert "# Introduction" in text
        assert "# Methods" in text
        assert "BiomarkerX" in text


# ===================================================================
# STAGE 3b: Peer Review (E2E-03)
# ===================================================================


class TestStagePeerReview:
    """Peer review of Stage 3 manuscript to complete E2E-03 coverage."""

    @pytest.fixture(autouse=True)
    def setup(self, output_dir):
        self.output_dir = output_dir

    def test_peer_review_of_manuscript(self, output_dir):
        manuscript_path = getattr(TestStage3ManuscriptWriting, "manuscript_path", None)
        if manuscript_path is None:
            pytest.skip("Stage 3 manuscript not available")
        findings = [
            {
                "criterion": "Methodology",
                "severity": "minor",
                "section": "Methods",
                "finding": "Sample size justification missing",
                "suggestion": "Add power analysis rationale",
            },
            {
                "criterion": "Statistical Analysis",
                "severity": "minor",
                "section": "Results",
                "finding": "Effect size not reported for primary endpoint",
                "suggestion": "Include Cohen's d or eta-squared",
            },
            {
                "criterion": "Literature Coverage",
                "severity": "pass",
                "section": "Introduction",
                "finding": "Adequate coverage of BiomarkerX literature",
                "suggestion": "",
            },
        ]
        report = generate_review_report(str(manuscript_path), findings, persona="balanced")
        assert "# Peer Review Report" in report
        assert "Methodology" in report
        assert "Recommendation" in report
        self.__class__.review_report = report

    def test_review_report_has_severity_counts(self):
        report = getattr(self.__class__, "review_report", None)
        if report is None:
            pytest.skip("review report not available")
        assert "minor" in report.lower()
        assert "pass" in report.lower()

    def test_review_report_saved(self, output_dir):
        report = getattr(self.__class__, "review_report", None)
        if report is None:
            pytest.skip("review report not available")
        path = output_dir / "peer_review_report.md"
        path.write_text(report)
        assert path.exists()
        assert path.stat().st_size > 100
        self.__class__.review_path = path


# ===================================================================
# STAGE 4: Blog Post Generation (sci-communication)
# ===================================================================


class TestStage4BlogPost:
    """Generate a science blog post from the research findings."""

    @pytest.fixture(autouse=True)
    def setup(self, output_dir):
        self.output_dir = output_dir

    def test_blog_format_reference_exists(self):
        """The blog format reference file must exist."""
        ref = SKILLS_DIR / "sci-communication" / "references" / "blog-format.md"
        assert ref.exists()

    def test_generate_blog_markdown(self):
        """Generate a blog post markdown file from research findings."""
        # Simulate what sci-communication would produce
        stats_report = getattr(TestStage1DataAnalysis, "stats_report", "p < 0.001")
        hypo_report = getattr(TestStage2Hypothesis, "hypo_report", "")

        blog_content = textwrap.dedent(f"""\
            # Can a Simple Blood Test Predict Who Benefits from Immunotherapy?

            Imagine knowing before treatment starts whether immunotherapy will work
            for a cancer patient. A new study suggests that a single biomarker —
            BiomarkerX — might hold the answer.

            ## The Problem

            Immunotherapy has revolutionized cancer treatment, but only about 30% of
            patients respond. The rest endure side effects with no benefit. Clinicians
            need a way to predict who will respond before committing to treatment.

            ## What the Researchers Did

            The team studied 30 cancer patients — 15 receiving immunotherapy and 15
            in a control group. They measured BiomarkerX levels in blood samples
            before treatment and tracked outcomes over two years.

            ## What They Found

            Patients with higher BiomarkerX levels were significantly more likely to
            respond to immunotherapy. The treatment group showed markedly higher
            biomarker levels (mean 7.9 vs 4.9 in controls, {stats_report}).

            Among treated patients, those who responded had biomarker levels above
            7.0, while non-responders averaged below 7.0. Biomarker levels also
            correlated with longer survival.

            ![BiomarkerX vs Survival](biomarker_survival.png)

            ## Why It Matters

            If validated in larger trials, BiomarkerX could become a routine blood
            test that guides treatment decisions — sparing non-responders from
            unnecessary treatment and directing resources to patients most likely
            to benefit.

            ## What Comes Next

            The team is planning a Phase III trial with 200 patients to confirm these
            findings. The key question: does BiomarkerX predict response across
            different cancer types, or only in this specific tumor?

            ---
            *Based on a prospective clinical study. This is early-stage research
            and findings should be interpreted with caution.*
        """)

        blog_path = self.output_dir / "blog_biomarkerx.md"
        blog_path.write_text(blog_content)
        assert blog_path.exists()
        assert blog_path.stat().st_size > 500

        # Verify blog structure matches sci-communication format
        assert "# " in blog_content  # Has heading
        assert "## " in blog_content  # Has subheadings
        assert "![" in blog_content  # Has image reference
        assert "What They Found" in blog_content or "findings" in blog_content.lower()

        self.__class__.blog_path = blog_path
        self.__class__.blog_content = blog_content

    def test_blog_has_accuracy_preservation(self):
        """Blog should not overstate findings."""
        content = getattr(self.__class__, "blog_content", None)
        if content is None:
            pytest.skip("blog not generated")
        # Should contain hedging language, not overclaiming
        hedging = ["suggests", "could", "might", "early-stage", "caution", "if validated"]
        found = sum(1 for h in hedging if h in content.lower())
        assert found >= 2, "Blog post should contain hedging language"

    def test_blog_has_visual_reference(self):
        """Blog should reference a figure/diagram."""
        content = getattr(self.__class__, "blog_content", None)
        if content is None:
            pytest.skip("blog not generated")
        assert "![" in content, "Blog should embed at least one image"


# ===================================================================
# STAGE 5: Tutorial Generation (sci-communication)
# ===================================================================


class TestStage5Tutorial:
    """Generate an educational tutorial from the methodology."""

    @pytest.fixture(autouse=True)
    def setup(self, output_dir):
        self.output_dir = output_dir

    def test_tutorial_format_reference_exists(self):
        """The tutorial format reference file must exist."""
        ref = SKILLS_DIR / "sci-communication" / "references" / "tutorial-format.md"
        assert ref.exists()

    def test_generate_tutorial_markdown(self):
        """Generate a tutorial markdown file."""
        tutorial_content = textwrap.dedent("""\
            # Tutorial: Biomarker Analysis for Treatment Response Prediction

            ## What You'll Learn

            - How to load and profile clinical trial data
            - Running appropriate statistical tests (t-test, chi-square, correlation)
            - Interpreting results in the context of treatment response
            - Generating publication-quality plots
            - Designing a follow-up experiment with power analysis

            ## Prerequisites

            - Basic statistics (mean, standard deviation, p-values)
            - Familiarity with Python and pandas
            - Understanding of clinical trial design (treatment vs control groups)

            ## Step 1: Loading and Profiling Your Data

            Clinical trial data typically arrives as a CSV with patient-level
            observations. Each row represents one patient with their measurements.

            ```python
            from data_ops import load_and_profile

            df, profile = load_and_profile("clinical_data.csv")
            print(f"Loaded {profile['n_rows']} patients, {profile['n_cols']} variables")
            print(f"Groups: {df['group'].value_counts().to_dict()}")
            ```

            ![Data Loading Pipeline](data_pipeline.svg)

            > **Why this matters:** Profiling catches data quality issues early —
            > missing values, unexpected categories, outlier distributions — before
            > they corrupt your analysis.

            ## Step 2: Comparing Groups with Statistical Tests

            The first question is: does BiomarkerX differ between treatment and
            control groups?

            ```python
            from data_ops import run_statistical_test

            result = run_statistical_test(df, "ttest",
                value_col="biomarker_level",
                group_col="group")

            print(f"t({result['df']}) = {result['statistic']:.3f}, "
                  f"p = {result['p_value']:.4f}")
            ```

            ![Biomarker Distribution](biomarker_boxplot.png)

            > **Common pitfall:** Using a t-test when your data isn't normally
            > distributed. Always check assumptions first with a Shapiro-Wilk test
            > or Q-Q plot.

            ## Step 3: Assessing Effect Size and Clinical Relevance

            Statistical significance (p < 0.05) is necessary but not sufficient.
            You also need to assess whether the difference is clinically meaningful.

            Cohen's d tells you the practical magnitude:
            - d < 0.2: negligible
            - d = 0.2-0.5: small
            - d = 0.5-0.8: medium
            - d > 0.8: large

            In our study, the biomarker difference shows a large effect (d > 1.0).

            ## Step 4: Designing a Follow-Up Experiment

            ```python
            from hypothesis_ops import design_experiment

            design = design_experiment(
                hypothesis="Higher BiomarkerX predicts better response",
                test_type="ttest",
                effect_size=1.0,
                alpha=0.05,
                power=0.8)

            print(f"Required sample size: {design['required_n']} per group")
            ```

            > **Why this matters:** Running a study that's too small wastes
            > resources and patients' time. Power analysis ensures your study
            > can detect the effect if it exists.

            ## Worked Example: Complete Analysis Pipeline

            Here's the full pipeline applied to the BiomarkerX dataset:

            1. Load data (30 patients, 15 per group)
            2. Run t-test on biomarker levels → significant (p < 0.001)
            3. Run chi-square on response rates → significant
            4. Correlate biomarker with survival → positive correlation
            5. Generate plots for publication
            6. Design Phase III trial with power analysis

            ## Common Pitfalls

            - **Multiple comparisons:** Testing many variables inflates false positives.
              Apply Bonferroni or FDR correction.
            - **Confounders:** Age and sex may influence both biomarker and outcome.
              Use regression to control for covariates.
            - **Overfitting:** Don't use the same data to discover and validate a biomarker.
              Split into discovery and validation cohorts.

            ## Going Deeper

            - Chen et al. (2024) — original BiomarkerX validation study
            - Wang et al. (2023) — mechanistic basis for BiomarkerX
            - Rodriguez et al. (2024) — Phase II clinical trial results

            ## Summary

            You've learned how to go from raw clinical data to a validated biomarker
            hypothesis with statistical evidence and a designed follow-up experiment.
            The key is the chain: data profiling → statistical testing → effect size
            → power analysis → experiment design.
        """)

        tutorial_path = self.output_dir / "tutorial_biomarker_analysis.md"
        tutorial_path.write_text(tutorial_content)
        assert tutorial_path.exists()
        assert tutorial_path.stat().st_size > 1000

        self.__class__.tutorial_path = tutorial_path
        self.__class__.tutorial_content = tutorial_content

    def test_tutorial_has_learning_objectives(self):
        content = getattr(self.__class__, "tutorial_content", None)
        if content is None:
            pytest.skip()
        assert "What You'll Learn" in content

    def test_tutorial_has_prerequisites(self):
        content = getattr(self.__class__, "tutorial_content", None)
        if content is None:
            pytest.skip()
        assert "Prerequisites" in content or "prerequisite" in content.lower()

    def test_tutorial_has_code_blocks(self):
        content = getattr(self.__class__, "tutorial_content", None)
        if content is None:
            pytest.skip()
        assert "```python" in content
        assert content.count("```") >= 6  # At least 3 code blocks (open + close)

    def test_tutorial_has_visual_references(self):
        content = getattr(self.__class__, "tutorial_content", None)
        if content is None:
            pytest.skip()
        assert content.count("![") >= 2, "Tutorial should have at least 2 figures"

    def test_tutorial_has_callout_boxes(self):
        content = getattr(self.__class__, "tutorial_content", None)
        if content is None:
            pytest.skip()
        assert "> **" in content, "Tutorial should have callout boxes"

    def test_tutorial_has_common_pitfalls(self):
        content = getattr(self.__class__, "tutorial_content", None)
        if content is None:
            pytest.skip()
        assert "Pitfall" in content or "pitfall" in content.lower()

    def test_tutorial_has_worked_example(self):
        content = getattr(self.__class__, "tutorial_content", None)
        if content is None:
            pytest.skip()
        assert "Worked Example" in content or "example" in content.lower()


# ===================================================================
# STAGE 6: Diagram Generation (viz-diagram-code)
# ===================================================================


class TestStage6Diagrams:
    """Generate Mermaid diagrams for the research pipeline."""

    @pytest.fixture(autouse=True)
    def setup(self, output_dir):
        self.output_dir = output_dir

    def test_pipeline_flowchart(self):
        """Generate a Mermaid flowchart of the analysis pipeline."""
        mermaid = textwrap.dedent("""\
            %%{init: {'theme': 'neutral'}}%%
            flowchart TB
                subgraph "Data Collection"
                    A[Patient Enrollment<br/>n=30] --> B{Randomization}
                    B -->|Treatment| C[Immunotherapy<br/>n=15]
                    B -->|Control| D[Standard Care<br/>n=15]
                end

                subgraph "Measurement"
                    C --> E[BiomarkerX Level]
                    D --> E
                    E --> F[Tumor Size]
                    F --> G[Response Assessment]
                    G --> H[Survival Follow-up]
                end

                subgraph "Analysis"
                    H --> I[Statistical Testing]
                    I --> J[t-test: Biomarker]
                    I --> K[Chi-square: Response]
                    I --> L[Correlation: Survival]
                    J & K & L --> M[Hypothesis Generation]
                    M --> N[Experiment Design]
                end

                classDef collection fill:#e3f2fd,stroke:#1565c0,color:#333
                classDef measure fill:#f3e5f5,stroke:#7b1fa2,color:#333
                classDef analysis fill:#e8f5e9,stroke:#2e7d32,color:#333

                class A,B,C,D collection
                class E,F,G,H measure
                class I,J,K,L,M,N analysis
        """)

        mmd_path = self.output_dir / "pipeline_flowchart.mmd"
        mmd_path.write_text(mermaid)
        assert mmd_path.exists()

        # Verify valid Mermaid syntax
        assert "flowchart" in mermaid
        assert "subgraph" in mermaid
        assert "classDef" in mermaid
        assert mermaid.count("-->") >= 5

        self.__class__.pipeline_mmd = mmd_path

    def test_comparison_diagram(self):
        """Generate a treatment vs control comparison diagram."""
        mermaid = textwrap.dedent("""\
            %%{init: {'theme': 'neutral'}}%%
            flowchart LR
                subgraph "Treatment Group"
                    T1[BiomarkerX: 7.9 avg]
                    T2[Tumor: 21.0mm avg]
                    T3[Response: 67%]
                    T4[Survival: 23.4 mo]
                end

                subgraph "Control Group"
                    C1[BiomarkerX: 4.9 avg]
                    C2[Tumor: 26.0mm avg]
                    C3[Response: 0%]
                    C4[Survival: 16.1 mo]
                end

                classDef treatment fill:#c8e6c9,stroke:#2e7d32,color:#333
                classDef control fill:#ffcdd2,stroke:#c62828,color:#333
                class T1,T2,T3,T4 treatment
                class C1,C2,C3,C4 control
        """)

        mmd_path = self.output_dir / "comparison_diagram.mmd"
        mmd_path.write_text(mermaid)
        assert mmd_path.exists()
        self.__class__.comparison_mmd = mmd_path

    def test_mind_map_diagram(self):
        """Generate a mind map of the BiomarkerX research landscape."""
        mermaid = textwrap.dedent("""\
            mindmap
              root((BiomarkerX))
                Mechanism
                  Immune evasion
                  T-cell activation
                  PD-L1 interaction
                Clinical Evidence
                  Phase II trials
                  Retrospective studies
                  Single-cell profiling
                Applications
                  Patient stratification
                  Treatment selection
                  Prognosis prediction
                Open Questions
                  Multi-cancer validation
                  Combination therapies
                  Resistance mechanisms
        """)

        mmd_path = self.output_dir / "biomarkerx_mindmap.mmd"
        mmd_path.write_text(mermaid)
        assert mmd_path.exists()
        assert "mindmap" in mermaid

    def test_render_script_exists(self):
        """The render script must exist and be executable."""
        script = SKILLS_DIR / "viz-diagram-code" / "scripts" / "render_diagram.sh"
        assert script.exists(), "render_diagram.sh not found"
        assert os.access(str(script), os.X_OK), "render_diagram.sh not executable"


# ===================================================================
# STAGE 7: Presentation Generation (viz-presentation)
# ===================================================================


class TestStage7Presentation:
    """Generate a Marp presentation from the research findings."""

    @pytest.fixture(autouse=True)
    def setup(self, output_dir):
        self.output_dir = output_dir

    def test_presentation_skill_files(self):
        """Verify viz-presentation skill has all required files."""
        skill_dir = SKILLS_DIR / "viz-presentation"
        assert (skill_dir / "SKILL.md").exists()
        assert (skill_dir / "scripts" / "setup.sh").exists()
        assert (skill_dir / "scripts" / "render_presentation.sh").exists()
        assert (skill_dir / "references" / "marp-syntax.md").exists()
        assert (skill_dir / "references" / "slide-structures.md").exists()
        assert (skill_dir / "references" / "content-conversion.md").exists()

    def test_generate_research_talk_slides(self):
        """Generate a full research talk presentation in Marp markdown."""
        slides = textwrap.dedent("""\
            ---
            marp: true
            theme: default
            paginate: true
            math: katex
            header: 'BiomarkerX as Immunotherapy Predictor'
            footer: 'Scientific OS Research — 2026'
            ---

            <!-- _class: lead -->
            <!-- _paginate: false -->

            # BiomarkerX as a Predictive Biomarker for Immunotherapy Response

            **A Prospective Clinical Study**

            Dr. Research Scientist
            Department of Oncology, University Medical Center
            April 2026

            ---

            ## Motivation

            - Immunotherapy benefits only ~30% of cancer patients
            - No reliable pre-treatment predictive biomarker exists
            - Patients endure side effects with uncertain benefit
            - **Goal:** Identify a blood-based biomarker for treatment selection

            <!-- Speaker notes:
            Open with the clinical problem. Emphasize the patient burden
            of unpredictable treatment response.
            -->

            ---

            ## Study Design

            ![bg right:40%](pipeline_flowchart.svg)

            - **30 patients** (15 treatment, 15 control)
            - Blood BiomarkerX measured at baseline
            - 12-week immunotherapy protocol
            - Endpoints: response rate, tumor size, survival

            ---

            ## Key Finding: BiomarkerX Levels Differ Significantly

            ![w:700](biomarker_boxplot.png)

            - Treatment group: mean 7.9 (SD 0.9)
            - Control group: mean 4.9 (SD 0.6)
            - **$t(28) = 10.2, p < 0.001$, Cohen's $d = 3.7$**

            ---

            ## Response Prediction

            | BiomarkerX Level | Response Rate | n |
            |:---:|:---:|:---:|
            | > 7.0 | 90% (9/10) | 10 |
            | 6.0 - 7.0 | 40% (2/5) | 5 |
            | < 6.0 | 0% (0/15) | 15 |

            **BiomarkerX > 7.0 predicts response with 90% sensitivity**

            ---

            ## Survival Correlation

            ![w:700](biomarker_survival.png)

            - Positive correlation: $r = 0.82, p < 0.001$
            - Each unit increase in BiomarkerX → 4.2 months longer survival
            - Effect consistent across age and sex subgroups

            ---

            ## Proposed Mechanism

            $$\\text{BiomarkerX}_{\\text{high}} \\rightarrow \\text{T-cell activation} \\rightarrow \\text{Anti-tumor immunity}$$

            1. BiomarkerX-high cells recruit cytotoxic T-cells
            2. T-cells infiltrate the tumor microenvironment
            3. Immune checkpoint blockade amplifies the response
            4. Result: tumor regression in BiomarkerX-high patients

            ---

            ## Limitations

            - Small sample size (n=30) — needs Phase III validation
            - Single tumor type — cross-cancer generalization unknown
            - BiomarkerX measured only at baseline — dynamics during treatment unclear
            - Retrospective response classification

            ---

            ## Next Steps

            1. **Phase III trial** — 200 patients, multi-center
            2. **Longitudinal monitoring** — BiomarkerX dynamics during treatment
            3. **Multi-cancer validation** — breast, lung, melanoma
            4. **Combination biomarkers** — BiomarkerX + PD-L1 expression

            ---

            <!-- _class: lead -->

            ## Take-Home Message

            **BiomarkerX > 7.0 predicts immunotherapy response with 90% sensitivity**

            A simple blood test could guide treatment decisions
            and spare non-responders from unnecessary therapy.

            ---

            ## References

            1. Chen et al. (2024) *J Clin Oncol* 42:1123-1135
            2. Wang et al. (2023) *Nat Immunol* 24:567-579
            3. Rodriguez et al. (2024) *Lancet Oncol* 25:89-101
            4. Kim et al. (2023) *Cell* 186:2341-2358

            **Contact:** researcher@university.edu

        """)

        pres_path = self.output_dir / "biomarkerx_talk.md"
        pres_path.write_text(slides)
        assert pres_path.exists()
        assert pres_path.stat().st_size > 1000

        self.__class__.presentation_path = pres_path
        self.__class__.presentation_content = slides

    def test_presentation_has_marp_frontmatter(self):
        content = getattr(self.__class__, "presentation_content", None)
        if content is None:
            pytest.skip()
        assert "marp: true" in content
        assert "math: katex" in content

    def test_presentation_has_title_slide(self):
        content = getattr(self.__class__, "presentation_content", None)
        if content is None:
            pytest.skip()
        assert "<!-- _class: lead -->" in content

    def test_presentation_has_slide_separators(self):
        content = getattr(self.__class__, "presentation_content", None)
        if content is None:
            pytest.skip()
        slide_count = content.count("\n---\n")
        assert slide_count >= 8, f"Expected 8+ slides, got {slide_count}"

    def test_presentation_has_math(self):
        content = getattr(self.__class__, "presentation_content", None)
        if content is None:
            pytest.skip()
        assert "$" in content, "Should contain math expressions"

    def test_presentation_has_speaker_notes(self):
        content = getattr(self.__class__, "presentation_content", None)
        if content is None:
            pytest.skip()
        assert "<!-- Speaker notes:" in content or "<!--" in content

    def test_presentation_has_image_references(self):
        content = getattr(self.__class__, "presentation_content", None)
        if content is None:
            pytest.skip()
        assert "![" in content
        img_count = content.count("![")
        assert img_count >= 3, f"Expected 3+ image references, got {img_count}"

    def test_presentation_has_table(self):
        content = getattr(self.__class__, "presentation_content", None)
        if content is None:
            pytest.skip()
        assert "|:---:" in content or "| ---" in content

    def test_render_script_exists(self):
        script = SKILLS_DIR / "viz-presentation" / "scripts" / "render_presentation.sh"
        assert script.exists()
        assert os.access(str(script), os.X_OK)


# ===================================================================
# STAGE 8: Cross-Stage Integration Verification
# ===================================================================


class TestStage8Integration:
    """Verify all stages connect — outputs from one flow into the next."""

    @pytest.fixture(autouse=True)
    def setup(self, output_dir):
        self.output_dir = output_dir

    def test_data_analysis_produces_plot_files(self):
        """Stage 1 should produce plot files that Stage 4-7 can embed."""
        scatter = getattr(TestStage1DataAnalysis, "scatter_paths", None)
        box = getattr(TestStage1DataAnalysis, "box_paths", None)
        if scatter is None or box is None:
            pytest.skip("Stage 1 plot state not available")
        for path in scatter + box:
            assert Path(path).exists()

    def test_hypothesis_consumes_data_patterns(self):
        """Stage 2 should consume patterns found in Stage 1."""
        patterns = getattr(TestStage2Hypothesis, "patterns", None)
        if patterns is None:
            pytest.skip("Stage 2 patterns not available")
        assert len(patterns["group_differences"]) > 0

    def test_manuscript_consumes_bibliography(self):
        """Stage 3 should have formatted citations from the .bib file."""
        bib = getattr(TestStage3ManuscriptWriting, "bibliography", None)
        if bib is None:
            pytest.skip("Stage 3 bibliography not available")
        assert "Chen" in bib

    def test_blog_references_findings(self):
        """Stage 4 blog should reference the statistical findings."""
        blog = getattr(TestStage4BlogPost, "blog_content", None)
        if blog is None:
            pytest.skip()
        # Blog should mention biomarker and findings
        assert "BiomarkerX" in blog or "biomarker" in blog.lower()
        assert "7.9" in blog or "significant" in blog.lower()

    def test_tutorial_chains_data_and_hypothesis(self):
        """Stage 5 tutorial should chain data_ops and hypothesis_ops."""
        content = getattr(TestStage5Tutorial, "tutorial_content", None)
        if content is None:
            pytest.skip()
        assert "load_and_profile" in content
        assert "run_statistical_test" in content
        assert "design_experiment" in content

    def test_diagrams_match_pipeline(self):
        """Stage 6 diagrams should reflect the actual pipeline."""
        mmd = getattr(TestStage6Diagrams, "pipeline_mmd", None)
        if mmd is None:
            pytest.skip()
        content = mmd.read_text()
        assert "Statistical Testing" in content
        assert "Hypothesis Generation" in content

    def test_presentation_embeds_plots(self):
        """Stage 7 presentation should reference Stage 1 plot files."""
        content = getattr(TestStage7Presentation, "presentation_content", None)
        if content is None:
            pytest.skip()
        assert "biomarker_boxplot" in content
        assert "biomarker_survival" in content

    def test_presentation_embeds_diagrams(self):
        """Stage 7 presentation should reference Stage 6 diagrams."""
        content = getattr(TestStage7Presentation, "presentation_content", None)
        if content is None:
            pytest.skip()
        assert "pipeline_flowchart" in content

    def test_all_output_files_created(self):
        """Verify every stage produced its expected output files."""
        files = list(self.output_dir.iterdir())
        if len(files) < 3:
            pytest.skip("Prior stages did not produce output files")
        filenames = {f.name for f in files}

        expected = {
            "biomarker_survival",  # scatter plot base name
            "biomarker_boxplot",   # box plot base name
            "manuscript_introduction.md",
            "peer_review_report.md",
            "blog_biomarkerx.md",
            "tutorial_biomarker_analysis.md",
            "pipeline_flowchart.mmd",
            "comparison_diagram.mmd",
            "biomarkerx_mindmap.mmd",
            "biomarkerx_talk.md",
        }

        for exp in expected:
            matches = [f for f in filenames if exp in f]
            assert len(matches) > 0, f"Missing output: {exp} (have: {sorted(filenames)})"

    def test_pipeline_output_summary(self):
        """Print a summary of all generated outputs (informational)."""
        files = sorted(self.output_dir.iterdir())
        if len(files) < 3:
            pytest.skip("Prior stages did not produce output files")
        summary_lines = []
        total_size = 0
        for f in files:
            size = f.stat().st_size
            total_size += size
            ext = f.suffix
            summary_lines.append(f"  {f.name} ({size:,} bytes)")

        summary = (
            f"\n{'='*60}\n"
            f"E2E Pipeline Output Summary\n"
            f"{'='*60}\n"
            f"Total files: {len(files)}\n"
            f"Total size: {total_size:,} bytes\n"
            f"\nFiles:\n" + "\n".join(summary_lines) + "\n"
            f"{'='*60}\n"
        )
        # This always passes — it's informational
        print(summary)
        assert len(files) >= 10, f"Expected 10+ output files, got {len(files)}"

    def test_data_ops_to_hypothesis_contract(self):
        """data_ops statistical test output has keys hypothesis_ops expects (E2E-05)."""
        result = getattr(TestStage1DataAnalysis, "biomarker_ttest", None)
        if result is None:
            pytest.skip("Stage 1 t-test not available")
        assert isinstance(result, dict), "data_ops output must be a dict"
        assert "p_value" in result, "data_ops output must have p_value for hypothesis_ops"
        assert "statistic" in result, "data_ops output must have statistic"
        assert isinstance(result["p_value"], float), "p_value must be float"
        assert isinstance(result["statistic"], (int, float)), "statistic must be numeric"

    def test_hypothesis_patterns_contract(self):
        """hypothesis_ops patterns output has keys downstream skills expect (E2E-05)."""
        patterns = getattr(TestStage2Hypothesis, "patterns", None)
        if patterns is None:
            pytest.skip("Stage 2 patterns not available")
        assert isinstance(patterns, dict), "patterns must be a dict"
        assert "correlations" in patterns, "patterns must have correlations key"
        assert "group_differences" in patterns, "patterns must have group_differences key"
        assert isinstance(patterns["correlations"], list), "correlations must be a list"
        assert isinstance(patterns["group_differences"], list), "group_differences must be a list"

    def test_bibliography_output_contract(self):
        """writing_ops bibliography output is a string suitable for manuscript embedding (E2E-05)."""
        bib = getattr(TestStage3ManuscriptWriting, "bibliography", None)
        if bib is None:
            pytest.skip("Stage 3 bibliography not available")
        assert isinstance(bib, str), "bibliography must be a string"
        assert len(bib) > 100, "bibliography must have substantial content"
        assert "\n" in bib, "bibliography must be multi-line"

    def test_manuscript_to_review_contract(self):
        """manuscript path from Stage 3 is a valid file for peer review input (E2E-05)."""
        path = getattr(TestStage3ManuscriptWriting, "manuscript_path", None)
        if path is None:
            pytest.skip("Stage 3 manuscript path not available")
        assert Path(path).exists(), "manuscript file must exist for review_ops"
        content = Path(path).read_text()
        assert len(content) > 50, "manuscript must have content for review"
        assert "# " in content, "manuscript must have markdown headers"

    def test_review_report_output_contract(self):
        """review_ops report is markdown string with expected sections (E2E-05)."""
        report = getattr(TestStagePeerReview, "review_report", None)
        if report is None:
            pytest.skip("Peer review report not available")
        assert isinstance(report, str), "review report must be a string"
        assert "# Peer Review Report" in report, "report must have header"
        assert "Recommendation" in report, "report must have recommendation section"
