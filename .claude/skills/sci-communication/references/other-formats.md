# Other Communication Formats

Reference for the sci-communication skill's lay-summary, press-release, newsletter, and conference poster abstract modes.

---

## Lay Summary

**Target length:** 300-500 words
**Audience:** Non-scientists -- patients, policymakers, journalists, general public
**Run through tool-humanizer:** NO (needs a distinct accessible voice, not standard blog humanization)

### Structure

1. **Why this research matters** (1-2 sentences) -- Start with what is relatable. Connect to health, daily life, or a problem people understand. "Every year, millions of people..." or "If you've ever wondered why..."

2. **What the problem was** (1 paragraph) -- Explain in simple terms what was not known or what needed solving. Frame it as a gap that affects real people.

3. **What the researchers did** (1 paragraph) -- Use analogy-based explanation. "Think of it like..." or "Imagine..." to make methods accessible. Focus on the approach, not the technique names.

4. **What they found** (1 paragraph) -- One key takeaway. Use comparisons rather than raw numbers. "People who received the treatment were twice as likely to recover" rather than "OR = 2.1, 95% CI 1.4-3.2."

5. **What this means for people** (1 paragraph) -- Real-world implications. How might this affect patients, policy, or understanding? Be honest about the timeline: "This is still early-stage research..." or "This could take 5-10 years to reach patients..."

### Tone

Accessible. Target a grade 8 reading level (Flesch-Kincaid ~60-70). No jargon -- if a technical term must be used, explain it immediately in parentheses. Short sentences (under 20 words preferred). Avoid passive voice. Use "you" and "we" to connect with the reader.

### Visual Placement

- One diagram after "What the researchers did" showing the concept or process visually
- Keep visuals simple -- labeled diagrams, not complex data plots

---

## Press Release Draft

**Target length:** 400-600 words
**Audience:** Journalists, institutional communications offices
**Run through tool-humanizer:** NO (press releases have their own formal conventions)

### Structure

1. **Headline** (1 line) -- Factual, specific, newsworthy. Not clickbait. "Researchers identify genetic marker linked to treatment response in breast cancer" rather than "Breakthrough discovery changes everything."

2. **Dateline + lead paragraph** (2-3 sentences) -- Who, what, where, when, why. The entire story in miniature. "[CITY, Date] -- Researchers at [Institution] have identified [finding], according to a study published in [Journal]."

3. **Quote from lead researcher** (1-2 sentences) -- Write a placeholder quote attributed to the first author. The quote should provide context or significance in the researcher's voice. Mark clearly: "[Placeholder -- replace with actual quote from author]"

4. **Background context** (1 paragraph) -- Why this research area matters. What was known before. Written for a journalist who may not have domain expertise.

5. **Key findings** (1-2 paragraphs) -- Main results, simplified for a general audience but with enough specificity for a journalist to report accurately. Include 1-2 specific numbers.

6. **Significance and next steps** (1 paragraph) -- What comes next? Broader implications. Timeline for clinical application if applicable (with appropriate hedging). Include a caveat about study limitations.

7. **Contact / institution information** (placeholder) -- "[Institution] press office: [placeholder email/phone]"

### Tone

Third person, formal but accessible. Newsworthy angle. Authoritative without being academic. Short sentences and paragraphs. Write so a journalist can pull quotes and facts directly into their article.

---

## Newsletter

**Target length:** 500-800 words
**Audience:** Field colleagues, lab members, department subscribers, science-interested professionals
**Run through tool-humanizer:** YES

### Structure

Use a recurring format with clear sections:

1. **Header** -- Newsletter name (use the user's if provided, otherwise "[Field] Update"), date, issue number if recurring.

2. **New this week** (2-3 items, 100-150 words each) -- Recent findings, preprints, or developments. Each item:
   - Bold one-line summary
   - 2-3 sentence explanation of the finding and why it matters
   - Link to the source paper or article
   - One sentence on implications or open questions

3. **Worth reading** (2-3 items, 50-75 words each) -- Papers, blog posts, or articles worth the reader's time. Each item:
   - Title and source
   - One sentence on why it is relevant
   - Link

4. **Tool spotlight** (1 item, 75-100 words) -- A tool, database, method, or resource useful for the field. Brief description of what it does and when to use it. Link.

5. **Sign-off** (1-2 sentences) -- Personal note from the researcher. Can reference upcoming events, ask for reader input, or tease next issue.

### Tone

Collegial and opinionated. The researcher's voice should come through -- this is a curated selection, not a neutral index. "I found this fascinating because..." is welcome. Keep it scannable -- readers should get value from skimming headings alone.

### For single-topic newsletters

If the user wants a newsletter about one finding rather than a roundup, use the blog format structure but with newsletter tone (more personal, more "here's what I think this means") and keep to 500-800 words.

---

## Conference Poster Abstract

**Target length:** 250 words (strict limit)
**Audience:** Conference attendees in the same or adjacent field
**Run through tool-humanizer:** NO (formal academic register required)

### Structure

1. **Background** (2-3 sentences) -- Context and rationale for the study.
2. **Objective** (1 sentence) -- Clear statement of the study aim.
3. **Methods** (2-3 sentences) -- Key methodological details. Include study design, sample size, and primary analysis.
4. **Results** (3-4 sentences) -- Main findings with key statistics (p-values, effect sizes, confidence intervals).
5. **Conclusions** (1-2 sentences) -- Take-home message and significance.

### Tone

Formal and concise. No hedging reduction from the original. Every word must earn its place given the 250-word limit. Use standard abbreviations without definition only if universally known in the field (DNA, RNA, PCR). This is an academic output -- maintain full scientific rigor.

### Accuracy Notes

- Report statistics exactly as in the original paper
- Do not simplify findings beyond what the 250-word limit requires
- Preserve all confidence intervals and p-values

---

## Accuracy Preservation Gate (All Formats)

**MANDATORY: Run this check before saving ANY content in these formats.**

1. **Every simplified claim must still be true.** Simplification is expected for lay summaries and press releases. Distortion is not.

2. **Preserve uncertainty.** "This early research suggests..." not "Scientists have discovered..." unless the finding is genuinely established consensus.

3. **Do not promise cures, treatments, or timelines** not present in the original source. This is especially critical for press releases and lay summaries, which may reach patients.

4. **Check headline against content.** Press release headlines are the most likely place for accuracy drift. The headline must be supported by the body text.

5. **Verify numbers.** Every statistic in the output must match the source. Do not round in ways that change meaning (49% -> "about half" is fine; 23% -> "about a quarter" is misleading).

6. **For newsletter roundups:** Each item is independently verified. A synthesis paragraph connecting multiple findings must not overstate the connection between independent studies.

---

## Format Selection Guide

When the user asks for communication content without specifying a format:

| User Says | Recommended Format(s) |
|-----------|----------------------|
| "Make this accessible" | Lay Summary + Blog Post |
| "I need to share this on social media" | Social Thread (see social-formats.md) |
| "Help me write a poster abstract" | Conference Poster Abstract |
| "I need a press release" | Press Release Draft |
| "Write a newsletter" | Newsletter |
| "Repurpose this for everything" | Blog Post + Social Thread + Lay Summary |
| "Help me explain this to a non-scientist" | Lay Summary or Explainer (see tutorial-format.md) |
| "I want to blog about my paper" | Blog Post (see blog-format.md) |
