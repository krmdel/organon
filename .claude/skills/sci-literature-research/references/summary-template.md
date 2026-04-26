# Structured Summary Template

## Template

```markdown
## [Paper Title]

**Authors:** [Author1, Author2, Author3 et al.]
**Journal:** [Journal Name] | **Year:** [Year] | **Citations:** [Count]
**DOI:** [DOI or "N/A"]

### Key Findings
- [Main result 1 -- extracted from abstract]
- [Main result 2]
- [Main result 3 if present]

### Methods
- [Methodology/approach described in abstract]

### Limitations
- [Limitations mentioned in abstract, or "Not specified in abstract" if none apparent]

### Relevance to Your Work
[1-2 sentences connecting this paper to the scientist's research interests, active questions, and field from research-profile.md. Reference specific interests or questions from the profile. OMIT this entire section if no research profile exists.]

**Sources:** [PubMed] [arXiv] [OpenAlex] [Semantic Scholar]
```

Only show source badges for databases that actually found this paper.

## Section Guidelines

### Key Findings
- Extract concrete results, numbers, and conclusions from the abstract
- Prioritize quantitative findings (e.g., "improved accuracy by 15%") over qualitative claims
- 2-4 bullet points, each one sentence
- If the abstract is very short, extract what is available and note "Limited abstract"

### Methods
- Describe the approach, not just the field
- Include: study design, data sources, analytical methods, sample sizes if mentioned
- Use active voice: "Used deep learning to classify..." not "Deep learning was used..."
- If no methods are apparent from the abstract, write "Methods not described in abstract"

### Limitations
- Look for hedging language: "however", "although", "further work needed", "preliminary"
- Check for sample size caveats, geographic restrictions, temporal limitations
- Note if the study is a preprint (not yet peer-reviewed)
- If no limitations are apparent, write "Not specified in abstract"

### Relevance to Your Work
- Be specific -- reference the scientist's exact interests from their research profile
- Connect to active research questions listed in the profile
- Mention how this paper's methods or findings could inform their work
- Example: "This paper's use of single-cell RNA-seq in tumor microenvironments directly addresses your active question about T cell exhaustion markers in colorectal cancer."

**When research profile is missing:** Omit the "Relevance to Your Work" section entirely. Do not add a placeholder. After the summary, mention: "Set up your research profile (`research profile`) to get personalized relevance assessments."

## Multiple Paper Summaries

When summarizing multiple papers in sequence, add a comparison section after all individual summaries:

```markdown
### Cross-Paper Comparison
- **Consensus:** [What the papers agree on]
- **Divergence:** [Where findings or methods differ]
- **Gap:** [What none of the papers address]
```
