"""Peer review report generation for sci-writing skill.

Generates structured markdown review reports with severity ratings.
Per D-13: output as structured markdown with sections for each criterion,
severity ratings, section references, and actionable suggestions.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root for repro import
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))
from repro.repro_logger import log_operation


SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2, "pass": 3}


def generate_review_report(
    manuscript_path: str,
    findings: list[dict],
    persona: str = "balanced",
) -> str:
    """Generate a structured peer review report in markdown.

    Args:
        manuscript_path: Path to the manuscript being reviewed.
        findings: List of dicts with keys: criterion, severity, section,
                  finding, suggestion. Severity is one of: critical, major,
                  minor, pass.
        persona: Reviewer persona (balanced, strict-methodologist,
                 clarity-editor, journal-reviewer).

    Returns:
        Formatted markdown report string.
    """
    filename = Path(manuscript_path).name
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Count severities
    counts = {"critical": 0, "major": 0, "minor": 0, "pass": 0}
    for f in findings:
        sev = f.get("severity", "minor").lower()
        if sev in counts:
            counts[sev] += 1

    lines = [
        "# Peer Review Report",
        "",
        f"**Manuscript:** {filename}",
        f"**Date:** {date_str}",
        f"**Reviewer Persona:** {persona}",
        "",
        "## Summary",
        "",
        f"- Critical: {counts['critical']} | Major: {counts['major']} "
        f"| Minor: {counts['minor']} | Pass: {counts['pass']}",
        "",
        "## Detailed Findings",
        "",
    ]

    # Group findings by criterion
    criteria_seen: list[str] = []
    grouped: dict[str, list[dict]] = {}
    for f in findings:
        c = f.get("criterion", "Unknown")
        if c not in grouped:
            criteria_seen.append(c)
            grouped[c] = []
        grouped[c].append(f)

    for i, criterion in enumerate(criteria_seen, 1):
        items = grouped[criterion]
        # Overall severity for this criterion is the worst finding
        worst = min(items, key=lambda x: SEVERITY_ORDER.get(x.get("severity", "pass").lower(), 3))
        worst_sev = worst.get("severity", "pass").upper()

        lines.append(f"### {i}. {criterion}")
        lines.append(f"**Status:** {worst_sev}")

        for item in items:
            sev = item.get("severity", "minor").upper()
            section = item.get("section", "N/A")
            finding = item.get("finding", "")
            suggestion = item.get("suggestion", "")

            if sev == "PASS":
                lines.append(f"**Section:** {section}")
                lines.append(f"**Finding:** {finding}")
            else:
                lines.append(f"**Section:** {section}")
                lines.append(f"**Finding:** [{sev}] {finding}")
                lines.append(f"**Suggestion:** {suggestion}")

        lines.append("")

    # Recommendation
    recommendation = _determine_recommendation(counts)
    lines.append("## Recommendation")
    lines.append(f"**Decision:** {recommendation}")
    lines.append("")

    return "\n".join(lines)


def _determine_recommendation(counts: dict) -> str:
    """Determine overall recommendation based on severity counts.

    Logic:
    - Any CRITICAL -> major revision or reject (>= 2 critical -> reject)
    - > 2 MAJOR -> major revision
    - Any MAJOR -> minor revision
    - Only MINOR or PASS -> accept or minor revision
    """
    if counts["critical"] >= 2:
        return "Reject"
    if counts["critical"] >= 1:
        return "Major Revision"
    if counts["major"] > 2:
        return "Major Revision"
    if counts["major"] >= 1:
        return "Minor Revision"
    if counts["minor"] >= 1:
        return "Minor Revision"
    return "Accept"


def generate_verified_review_report(
    manuscript_path: str,
    bib_path: str,
    source_path: str | None = None,
    extra_findings: list[dict] | None = None,
    persona: str = "balanced",
    apply_fixes: bool = True,
) -> dict:
    """Run programmatic verification then merge with any AI-supplied findings.

    Delegates to verify_ops.run_verification — `bib_path` is REQUIRED by the
    underlying gate. See verify_ops.VerificationError for refusal semantics.

    Args:
        manuscript_path: Path to the manuscript .md file.
        bib_path: .bib file for citation key matching + CrossRef integrity (REQUIRED).
        source_path: Optional source material for hedging comparison + quote check.
        extra_findings: Optional list of AI-generated findings to merge in.
        persona: Reviewer persona for the report header.
        apply_fixes: Whether to write auto-fixes back to the manuscript.

    Returns:
        Dict with keys:
            report:      The markdown review report string.
            findings:    Combined findings list.
            auto_fixes:  Auto-fixes applied by verify_ops.
            summary:     Severity counts.
            blocked:     True if CRITICAL findings exist (caller MUST NOT save).
    """
    # Local import so review_ops can be used standalone if verify_ops is missing
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from verify_ops import run_verification

    verification = run_verification(
        manuscript_path,
        bib_path=bib_path,
        source_path=source_path,
        apply_fixes=apply_fixes,
    )

    findings = list(verification["findings"])
    if extra_findings:
        findings.extend(extra_findings)

    report = generate_review_report(manuscript_path, findings, persona=persona)

    return {
        "report": report,
        "findings": findings,
        "auto_fixes": verification["auto_fixes"],
        "summary": verification["summary"],
        "blocked": verification.get("blocked", False),
    }


def save_review(
    report: str,
    manuscript_name: str,
    output_dir: str = "projects/sci-writing",
) -> str:
    """Save a review report to disk and log the operation.

    Args:
        report: The markdown review report content.
        manuscript_name: Name of the reviewed manuscript (used in filename).
        output_dir: Directory to save the review in.

    Returns:
        Absolute path to the saved review file.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Clean manuscript name for filename
    clean_name = manuscript_name.replace(" ", "-").replace("/", "-").lower()
    if clean_name.endswith(".md"):
        clean_name = clean_name[:-3]

    out_path = Path(PROJECT_ROOT) / output_dir
    out_path.mkdir(parents=True, exist_ok=True)
    filepath = out_path / f"{date_str}_{clean_name}_review.md"
    filepath.write_text(report, encoding="utf-8")

    log_operation(
        skill="sci-writing",
        operation="review",
        params={"manuscript": manuscript_name, "output": str(filepath)},
        output_files=[str(filepath)],
    )

    return str(filepath)
