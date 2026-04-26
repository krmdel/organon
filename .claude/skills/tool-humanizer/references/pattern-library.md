# AI Pattern Library

50+ detectable AI writing patterns organized by category. Each pattern includes detection criteria and severity (high = almost always AI, medium = suspicious, low = sometimes human too).

---

## 1. AI Cliches & Openers (18 patterns) — Severity: HIGH

These are near-certain AI tells. Humans almost never write these unprompted.

| Pattern | Example |
|---------|---------|
| Fast-paced world opener | "In today's fast-paced world..." / "In today's rapidly evolving landscape..." |
| Dive/explore invitation | "Let's dive deep into..." / "Let's explore..." |
| Unlock/unleash | "Unlock your potential" / "Unleash the power of" |
| Harness the power | "Harness the power of AI/data/technology" |
| No secret opener | "It's no secret that..." |
| Key takeaway | "The key takeaway is..." |
| End of the day | "At the end of the day..." |
| Game-changer | "This is a game-changer" / "paradigm shift" |
| Crucial/critical + understand | "It's crucial to understand that..." |
| Journey metaphor | "On this journey..." / "As we navigate..." |
| Landscape metaphor | "The [X] landscape" / "In the [X] landscape" |
| Tapestry/mosaic metaphor | "A rich tapestry of..." / "The tapestry of..." |
| Realm of | "In the realm of..." |
| Beacon of | "A beacon of hope/innovation/progress" |
| Testament to | "A testament to..." / "stands as a testament" |
| Cornerstone | "[X] is the cornerstone of..." |
| Bustling | "The bustling streets/city/marketplace" |
| Resonate/reverberate | "This resonates deeply..." / "reverberates through" |

## 2. Hedging Language (8 patterns) — Severity: MEDIUM

AI hedges constantly to avoid commitment. Humans hedge too, but AI does it systematically.

| Pattern | Detection rule |
|---------|---------------|
| "It's important to note" | Almost always removable without losing meaning |
| "It's worth mentioning" | Same — throat-clearing before the actual point |
| "One might argue" | Passive attribution to nobody |
| Vague quantifiers | "various", "numerous", "myriad", "plethora", "a myriad of" |
| "Arguably" overuse | More than once per 500 words |
| "Potentially" padding | "This could potentially..." — double hedge |
| "It should be noted" | Passive filler |
| "Interestingly" / "Notably" | AI uses these as emphasis markers humans rarely do |

## 3. Corporate Buzzwords (12 patterns) — Severity: MEDIUM-HIGH

| AI word | Human replacement |
|---------|------------------|
| "utilize" | "use" |
| "facilitate" | "help" / "make easier" |
| "optimize" | "improve" / "make better" |
| "leverage" | "use" |
| "synergize" | "work together" |
| "ideate" | "brainstorm" / "think through" |
| "incentivize" | "encourage" / "reward" |
| "operationalize" | "put into practice" / "actually do" |
| "circle back" | "follow up" / "come back to" |
| "move the needle" | "improve results" / "make a difference" |
| "bandwidth" (for capacity) | "time" / "capacity" |
| "low-hanging fruit" | "easy wins" / "quick fixes" |

## 4. Robotic Structure (9 patterns) — Severity: HIGH

| Pattern | What to look for |
|---------|-----------------|
| Rhetorical Q+A | Question immediately followed by its answer in the next sentence |
| Obsessive parallelism | 3+ consecutive sentences starting the same way |
| Always-three lists | Every list has exactly 3 items — humans vary |
| "Here are the top X" | List prefacing announcement |
| Announcement of emphasis | "Importantly," "Crucially," "Significantly," at sentence start |
| Section summary + preview | "Now that we've covered X, let's look at Y" |
| Formulaic conclusions | "In conclusion," "To summarize," "In summary," |
| Mirror structure | Every paragraph follows identical structure (claim, evidence, conclusion) |
| Numbered everything | Numbering items that don't need ordering |

## 5. Overused Transitions (14 patterns) — Severity: MEDIUM

Flag when density exceeds 3 per 500 words:

- "Moreover,"
- "Furthermore,"
- "Additionally,"
- "Nevertheless,"
- "Consequently,"
- "Subsequently,"
- "Conversely,"
- "Notwithstanding,"
- "In light of this,"
- "With that said,"
- "That being said,"
- "Having said that,"
- "It is worth noting that"
- Excessive "However" (more than 2 per 500 words)

## 6. Promotional Inflation (8 patterns) — Severity: HIGH

| Pattern | Why it's AI |
|---------|------------|
| "Transformative" | Humans rarely use this outside press releases |
| "Unprecedented" | Massively overused by AI for anything slightly new |
| "Revolutionary" | Almost never warranted |
| "Cutting-edge" | Meaningless superlative |
| "State-of-the-art" | Same |
| "Groundbreaking" | Rarely accurate |
| "Comprehensive" (as praise) | "A comprehensive guide/solution/approach" — AI loves this |
| "Robust" (for anything non-technical) | "A robust strategy" — AI favourite |

## 7. Wikipedia/Academic AI Tells (from Wikipedia "Signs of AI writing") — Severity: MEDIUM-HIGH

| Pattern | Description |
|---------|------------|
| Inflated symbolism | Treating ordinary subjects with grandiose language — "the enduring legacy of [mundane thing]" |
| Em dash overuse | More than 2 em dashes per 500 words in non-literary text |
| Rule of three | Everything comes in threes — "X, Y, and Z" pattern repeated through the piece |
| Vague attributions | "Many experts believe..." / "Studies have shown..." / "Scholars argue..." with no citation |
| Negative parallelisms | "Not just X, but Y" / "Not merely X, but also Y" — AI uses this constantly |
| Superficial -ing analyses | "[Topic], reflecting [vague observation]" — surface-level analysis disguised as insight |
| Excessive conjunctive phrases | "On the other hand," "In addition to this," "As a result of this," stacking |
| Delve | "Let's delve into..." / "delving deeper" — one of the highest-confidence AI vocabulary tells |
| Multifaceted | "A multifaceted approach/issue/challenge" |
| Nuanced | "A nuanced understanding/perspective" — AI uses this 50x more than humans |
| Foster | "Foster innovation/growth/collaboration" |
| Underscore | "This underscores the importance of..." |
| Pivotal | "A pivotal moment/role/development" |
| Spearheaded | "She spearheaded the initiative" |

## 8. AI Vocabulary Tells — Severity: HIGH

Words that appear 10-50x more frequently in AI text than human text:

**Highest confidence (near-certain AI):**
delve, tapestry, multifaceted, nuanced, landscape (metaphorical), realm, beacon, testament, cornerstone, bustling, foster, underscore, pivotal, spearheaded, embark, meticulous, intricate, commendable, noteworthy

**High confidence:**
paramount, indispensable, invaluable, exemplary, adept, unwavering, groundbreaking, holistic, synergy, catalyst, resonate, reverberate, encompass, culminate

**Medium confidence (context-dependent):**
robust (non-technical), comprehensive (as praise), streamline, enhance, empower, innovative, strategic, dynamic, sustainable, leverage

---

## Detection Priority

When scanning, check in this order (highest-impact first):
1. AI vocabulary tells (Section 8) — fastest signal
2. AI cliches & openers (Section 1) — most obvious
3. Robotic structure (Section 4) — hardest for humans to miss
4. Corporate buzzwords (Section 3) — easy replacements
5. Promotional inflation (Section 6) — easy replacements
6. Wikipedia tells (Section 7) — subtler patterns
7. Hedging language (Section 2) — context-dependent
8. Overused transitions (Section 5) — density-dependent
