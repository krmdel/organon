# Blog Post Format

Reference for the sci-communication skill's blog mode. Covers structure, tone, accuracy gates, and visual placement for science blog posts.

---

## Structure

1. **Hook** (2-3 sentences) -- Why should the reader care? Start with the implication, not the method. What changes because of this research or concept? Lead with what is surprising, counterintuitive, or consequential.

2. **Background** (1-2 paragraphs) -- Simple context. No jargon. Explain the problem or gap this topic addresses in everyday terms. Use analogies where helpful. If writing from a concept (not a paper), set up why the concept matters now.

3. **The core idea** (1-2 paragraphs) -- What is the concept, finding, or insight?
   - For paper-based posts: What did the researchers do and find? Simplified methods ("The team analyzed blood samples from 500 patients" not "PBMCs were isolated via Ficoll gradient centrifugation"). Key results with 1-2 specific numbers. Use comparisons ("twice as likely", "30% reduction") rather than raw statistics.
   - For concept-based posts: What is this and how does it work? Build understanding layer by layer. Start with the intuition, then add detail.

4. **Why it matters** (1 paragraph) -- Real-world implications. Connect the finding or concept to something the reader's life, field, or society. Be specific about impact rather than vague ("could change medicine" -> "could reduce diagnostic wait times from weeks to hours").

5. **What comes next** (1 paragraph) -- Open questions, future directions, limitations. This is where hedging lives naturally -- frame uncertainty as exciting rather than disappointing. "The big question now is..." rather than "Unfortunately, this study was limited by..."

6. **Call-to-action** (1-2 sentences) -- Link to the full paper if applicable. Invite comments or questions. Keep it brief.

**Visual placement:** At least one diagram or illustration after the core idea section. A second visual in the background section is encouraged if the concept is spatial or process-based.

---

## Specifications

- **Target length:** ~1000 words
- **Audience:** Educated general public, science-curious readers, professionals in adjacent fields
- **Tone:** Conversational but authoritative. Use "you" to address the reader. Short paragraphs (3-5 sentences). Subheadings encouraged for scannability. Analogies are a primary tool -- find one good analogy per post.
- **Run through tool-humanizer:** YES

---

## Accuracy Preservation Gate

**MANDATORY: Run this check before saving ANY blog post.**

Before finalizing output, perform this self-verification:

1. **List every factual claim** in the blog post (numbers, findings, conclusions, mechanism descriptions).
2. **Verify each claim exists in the source material.** Flag any claim that cannot be traced to a specific source passage, paper, or established scientific consensus.
3. **Check that no hedging was removed.** Compare qualifier words:
   - Source: "suggests" -> Blog: "proves" = FLAGGED
   - Source: "may be associated with" -> Blog: "causes" = FLAGGED
   - Source: "preliminary evidence" -> Blog: "definitive proof" = FLAGGED
4. **Check that no unsupported conclusions were added.** The blog should not claim more than the source supports.
5. **Flag any claim that adds certainty not present in the original.** Even subtle upgrades ("indicates" -> "demonstrates") should be noted for author review.

**Output:** Either "PASS -- all claims verified against source" or a list of flagged claims with the original language and the blog language side by side.

**If claims are flagged:** Revise the blog to match the source's certainty level before saving. Do not save content with unflagged accuracy issues.

**For concept-based posts (no single source):** Verify claims against established scientific consensus. Flag any claim that is contested, preliminary, or field-specific rather than settled. Note these for the author: "This claim reflects the current consensus in [field] but is actively debated."

---

## Citation Simplification

Scientific papers use formal citations that are inaccessible to general audiences. Replace them with natural language references.

| Original Citation | Simplified Version | When to Use |
|-------------------|--------------------|-------------|
| (Smith et al., 2024) | "A recent study by researchers at [Institution]" | When institution is known and notable |
| (Smith & Doe, 2024; Lee, 2023) | "Multiple studies have shown" or "Several research teams have found" | When grouping findings from multiple papers |
| Smith (2024) demonstrated... | "Researchers led by [Name] at [Institution]..." | When the author is notable or adds credibility |
| [1-3] or (1-3) | "Previous research" or "A body of evidence" | When citing a range of supporting studies |
| (reviewed in Smith, 2024) | "According to a recent review of the evidence" | When citing review articles |

### Guidelines

- **Use institution names** when they add credibility (Harvard, MIT, WHO, NIH)
- **Use "researchers" or "scientists"** as the generic fallback
- **Preserve the number of studies** when relevant: "Three independent studies have confirmed..." rather than just "Studies show..."
- **Keep the year** when recency matters: "A 2024 study found..." is more specific than "Recent research shows..."
- **Never fabricate institutions** -- if you do not know the institution, use "researchers" generically

---

## Common Mistakes to Avoid

- Starting with "In recent years..." or "Scientists have long known..." -- these are AI-tell openers
- Overusing "groundbreaking", "revolutionary", "paradigm-shifting" -- let the finding speak for itself
- Burying the most interesting finding in paragraph 4 -- lead with it
- Writing a methods section disguised as a blog paragraph -- simplify radically
- Ending with "Only time will tell..." or "The future looks bright..." -- be specific about what comes next
