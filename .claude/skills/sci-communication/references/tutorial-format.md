# Tutorial and Explainer Format

Reference for the sci-communication skill's tutorial and explainer modes. Covers structure for teaching scientific concepts, methods, and techniques to non-expert audiences.

---

## Tutorial Format

For "how-to", "teach me", "gentle introduction", "step by step" requests.

### Structure

1. **What you'll learn** (3-5 bullet points) -- Learning objectives upfront. Be specific: "How to interpret a volcano plot" not "Understanding data visualization." The reader should know exactly what they will be able to do after reading.

2. **Prerequisites** (brief, 2-4 lines) -- What the reader should already know. Be honest -- if this requires stats background, say so. Suggest where to learn prerequisites if possible.

3. **Concept introduction** (1-2 paragraphs) -- Intuitive explanation with analogy. Start from what the reader already knows and bridge to the new concept. The analogy should carry through the tutorial as a reference point.

4. **Step-by-step walkthrough** -- Numbered steps with:
   - Clear explanation of each step in plain language
   - Code examples if computational (with language tags and comments)
   - **"Why this step matters"** callout after non-obvious steps -- one sentence explaining motivation
   - Visual diagram at key conceptual transitions (see Visual Placement below)
   - Expected output or result after each major step

5. **Worked example** -- Complete example applying the concept end-to-end. Use realistic data or scenarios from the target field. Show the full process, not just the happy path -- include what to do when something looks wrong.

6. **Common pitfalls** (3-5 items) -- What usually goes wrong and how to avoid it. Format as:
   - **Pitfall:** [what happens]
   - **Why:** [root cause]
   - **Fix:** [what to do instead]

7. **Going deeper** -- Links to papers, textbooks, resources, advanced topics. Organized by difficulty: "Next steps" (intermediate) and "Deep dive" (advanced).

### Visual Placement

- **After concept introduction:** A diagram showing the overall idea or process before diving into steps
- **At each major step transition:** A diagram showing what just happened and what comes next
- **In the worked example:** An output visualization showing the expected result
- Minimum 2 visuals for any tutorial. Complex topics should have 3-5.

### Specifications

- **Target length:** 1500-3000 words depending on complexity
- **Audience:** Students, junior researchers, scientists from adjacent fields
- **Tone:** Patient, encouraging, technically precise but accessible. Use "we" to include the reader ("Now we'll look at..."). Acknowledge difficulty without discouraging ("This part is tricky, but the key insight is...").
- **Run through tool-humanizer:** NO (tutorial voice is already distinct from AI-generic)

---

## Explainer Format

For "explain this concept", "what is X", "ELI5", "for non-scientists" requests. Shorter and more focused than tutorials -- explains what something IS rather than how to DO it.

### Structure

1. **One-sentence answer** -- If someone asked "what is [concept]?", answer in one clear sentence. This is the takeaway.

2. **The analogy** (1 paragraph) -- An everyday analogy that captures the core mechanism. The best analogies are ones where the reader says "oh, it's like..." and carries the understanding forward.

3. **How it actually works** (2-3 paragraphs) -- Layer detail onto the analogy. Start simple, add complexity. Use "imagine..." and "think of it as..." to build understanding. Introduce technical terms only after the concept is clear -- then the term becomes a label for something already understood.

4. **Why it matters** (1 paragraph) -- Real-world significance. Why should a non-expert care? Connect to health, technology, daily life, or big questions.

5. **The nuance** (1 paragraph) -- What the simple explanation leaves out. Be honest about complexity without overwhelming. "The real picture is more complicated because..." followed by one key nuance.

6. **One thing to remember** (1-2 sentences) -- The single takeaway. If the reader forgets everything else, what should stick?

### Visual Placement

- **After the analogy:** A diagram that makes the analogy visual
- **In "How it actually works":** A diagram showing the real mechanism, labeled accessibly

### Specifications

- **Target length:** 500-800 words
- **Audience:** Complete non-experts, curious general public, students encountering the concept for the first time
- **Tone:** Warm, clear, zero jargon until explained. Short sentences. Active voice. If a 12-year-old could not follow the explanation, it needs simplification.
- **Run through tool-humanizer:** NO

---

## Accuracy Preservation Gate (Both Formats)

**MANDATORY for tutorials and explainers.**

Simplification is expected and necessary. Distortion is not.

1. **Every simplified claim must still be true.** "Cells talk to each other using chemical signals" is a valid simplification. "Cells decide what to do" implies agency that is misleading.

2. **Analogies must not create false understanding.** After using an analogy, note where it breaks down: "Unlike [analogy], [concept] also [key difference]." One sentence is enough.

3. **Technical terms must be used correctly.** If you introduce a term, its definition must be accurate even if simplified.

4. **Uncertainty must be preserved.** "Scientists think..." or "Current evidence suggests..." -- not "We know that..." unless the claim is genuinely settled consensus.

5. **Scope must be honest.** If the tutorial covers a simplified version of a method, say so: "This is the basic version. Production implementations also handle [X] and [Y]."

---

## Code Example Guidelines (Tutorials Only)

When tutorials include code:

- Use Python unless the user specifies another language
- Include comments explaining WHY, not just WHAT
- Show imports at the top of the first code block
- Use realistic variable names (not `x`, `y`, `foo`)
- Show expected output after each code block
- If using libraries, note the install command: `pip install [package]`
- Keep individual code blocks under 20 lines -- break long processes into steps
- Test that code logic is correct (even if you cannot run it, verify the approach)
