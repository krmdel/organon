# Research Profile Schema

This document defines the structure of `research_context/research-profile.md`. The profile is created by the `sci-research-profile` skill during interactive onboarding and read by downstream scientific skills.

## Template

```markdown
# Research Profile

## Core Identity
- **Name:** [Full name]
- **Institution:** [University/Lab]
- **Department:** [Department/Division]
- **Career Stage:** [PhD Student | Postdoc | Assistant Prof | Associate Prof | Full Prof | Industry Researcher | Research Scientist | Other]

## Research Focus
- **Primary Field:** [e.g., Computational Biology]
- **Subfields:** [e.g., Genomics, Protein Structure Prediction]
- **Keywords:** [comma-separated research keywords]
- **Active Questions:**
  1. [Current research question]
  2. [Current research question]

## Preferences
- **Preferred Journals:** [e.g., Nature Methods, Bioinformatics, PNAS]
- **Citation Style:** [APA | Nature | IEEE | Vancouver | Chicago]
- **Writing Conventions:** [e.g., passive voice, Oxford comma, American English]

## Tool Ecosystem
- **Languages:** [e.g., Python, R, MATLAB]
- **Statistical Tools:** [e.g., scipy, statsmodels, R/lme4]
- **Databases:** [e.g., UniProt, PDB, GEO, TCGA]
- **Other:** [e.g., Docker, Nextflow, Snakemake]
```

## Field Reference

### Core Identity

| Field | Required | Valid Values | Default |
|-------|----------|-------------|---------|
| Name | Yes | Free text | Not specified |
| Institution | Yes | Free text | Not specified |
| Department | Yes | Free text | Not specified |
| Career Stage | Yes | PhD Student, Postdoc, Assistant Prof, Associate Prof, Full Prof, Industry Researcher, Research Scientist, Other | Not specified |

### Research Focus

| Field | Required | Format | Default |
|-------|----------|--------|---------|
| Primary Field | Yes | Free text | Not specified |
| Subfields | No | Comma-separated list | Not specified |
| Keywords | No | Comma-separated list | Not specified |
| Active Questions | No | Numbered list | Not specified |

### Preferences

| Field | Required | Valid Values | Default |
|-------|----------|-------------|---------|
| Preferred Journals | No | Comma-separated list | Not specified |
| Citation Style | No | APA, Nature, IEEE, Vancouver, Chicago | Not specified |
| Writing Conventions | No | Free text | Not specified |

### Tool Ecosystem

| Field | Required | Format | Default |
|-------|----------|--------|---------|
| Languages | No | Comma-separated list | Not specified |
| Statistical Tools | No | Comma-separated list | Not specified |
| Databases | No | Comma-separated list | Not specified |
| Other | No | Comma-separated list | Not specified |

## Parsing Rules

- Each section starts with `## Section Name`
- Fields within sections use `- **Label:** value` format
- Active Questions use numbered list format: `  1. question text`
- "Not specified" indicates the user skipped or didn't provide that field
- Downstream skills should treat "Not specified" as absent data and fall back to generic behavior
