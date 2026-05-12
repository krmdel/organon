/**
 * Phase 7 (fix-sprint) T6.10 / T6.11 — lightweight query classifier.
 *
 * Closes DOGFOOD #1: federated search with arXiv enabled returned
 * ML/math weight-similarity preprints in the top-4 for "GLP-1 obesity
 * meta-analysis", crowding out the actual systematic-review-of-trials
 * the researcher needed. The fix is twofold:
 *
 *   1. When a query is biomedical AND the caller didn't pin sources,
 *      default-off arXiv (still a one-click toggle in the UI).
 *   2. When arXiv IS explicitly enabled on a biomedical query, post-rank
 *      arXiv-only results below PubMed / OpenAlex / S2 hits so they don't
 *      monopolize the top of the page.
 *
 * The classifier is deliberately conservative: any single keyword hit
 * promotes a query. A handful of false positives are a much better
 * trade-off than missing a clinical-trial review for the dogfood case
 * the report flagged.
 */

const BIOMEDICAL_KEYWORDS = [
  // Clinical / epidemiology
  "patient", "patients", "trial", "trials", "rct", "placebo",
  "cohort", "efficacy", "treatment", "treatments", "incidence",
  "prevalence", "morbidity", "mortality", "diagnosis", "prognosis",
  "biomarker", "biomarkers", "epidemiology", "epidemiological",
  "meta-analysis", "systematic review",
  // Disease classes
  "cancer", "tumor", "tumour", "carcinoma", "leukemia", "lymphoma",
  "diabetes", "obesity", "metabolic", "cardiovascular",
  "alzheimer", "parkinson", "dementia",
  "covid", "sars-cov", "influenza", "asthma", "copd", "tuberculosis",
  "ischemic", "ischemia", "myocardial", "stroke", "hypertension",
  "atherosclerosis", "inflammation", "infection", "sepsis",
  "lupus", "psoriasis", "ibd",
  // Common drugs / classes
  "glp-1", "tirzepatide", "semaglutide", "metformin", "insulin",
  "antibody", "antibodies", "vaccine", "immunotherapy",
  "chemotherapy", "antibiotic", "anticoagulant",
  // Biology / molecular
  "gene", "genes", "genetic", "genome", "transcript", "transcriptome",
  "protein", "proteins", "peptide", "receptor", "receptors",
  "pathway", "pathways", "kinase", "epigenetic", "epigenetics",
  "rna", "dna", "mrna", "microrna",
  "neuron", "neurons", "synapse", "synapses", "neural",
  "microbiome", "microbiota", "cytokine", "lymphocyte",
  "tcell", "t-cell", "b-cell", "macrophage",
  "tissue", "organ", "fibroblast",
  // Registries / databases
  "clinicaltrials", "nct", "pubmed", "ncbi",
];

// Min 2 leading letters keeps short prefixes like "omeprazole" matchable
// (ome + prazole = 10 chars, classic short-prefix INN). Drug-suffix specificity
// makes false positives rare even with the relaxed prefix.
const DRUG_SUFFIX_RE = /\b[a-z]{2,}(?:mab|nib|tide|prazole|gliptin|sartan|statin|cycline|olol|parin|mycin|cillin)\b/i;

const BIOMEDICAL_FIELD_FRAGMENTS = [
  "biomed", "biolog", "medic", "clinic", "pharm", "health",
  "neuro", "onco", "epidem", "physiol", "molecular", "cancer",
  "immun", "genetic", "genom", "microbio", "endocrin", "card",
];

const NON_BIOMEDICAL_FIELD_FRAGMENTS = [
  "math", "physic", "comp sci", "computer sci", "ml", "machine learn",
  " ai ", "artificial intelligence", "engineer", "robot", "graphic",
  "linguistic", "econom", "social sci", "education",
];

/**
 * Decide whether a free-form query is biomedical.
 *
 * Lookup order:
 *   1. Explicit `field` (project metadata) wins — fragments like
 *      "biomedical", "neuroscience", "oncology" → biomedical;
 *      "machine learning", "physics" → non-biomedical.
 *   2. Drug-name suffix sniff (any token ending in -mab, -nib, …).
 *   3. Keyword hit count ≥ 1 over the BIOMEDICAL_KEYWORDS list.
 *
 * False positives are acceptable and far cheaper than false negatives —
 * a misclassified comp-sci query just sees PubMed first, which is
 * harmless. A misclassified biomedical query sees arXiv first, which is
 * exactly the bug DOGFOOD #1 reported.
 */
export function isBiomedicalQuery(query: string, field?: string | null): boolean {
  if (field && field.trim().length > 0) {
    const f = ` ${field.toLowerCase()} `;
    if (NON_BIOMEDICAL_FIELD_FRAGMENTS.some((frag) => f.includes(frag))) return false;
    if (BIOMEDICAL_FIELD_FRAGMENTS.some((frag) => f.includes(frag))) return true;
  }
  if (DRUG_SUFFIX_RE.test(query)) return true;
  const q = ` ${query.toLowerCase()} `;
  for (const kw of BIOMEDICAL_KEYWORDS) {
    // Use word-boundary-aware substring match so "gene" doesn't match "gene-ral".
    const padded = kw.includes(" ") || kw.includes("-")
      ? q.includes(kw)
      : new RegExp(`(^|[^a-z])${kw.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}([^a-z]|$)`, "i").test(query);
    if (padded) return true;
  }
  return false;
}

/**
 * Reorder a list of papers (each with a `sources_merged` list) so that
 * arXiv-only entries land at the bottom while still preserving the
 * original ranking within the two halves. Used after the composite-
 * score sort when arXiv is on but the query is biomedical.
 */
export function rerankByDomain<T extends { sources_merged: string[] }>(
  papers: T[],
  biomedical: boolean,
): T[] {
  if (!biomedical) return papers;
  const arxivOnly: T[] = [];
  const others: T[] = [];
  for (const p of papers) {
    if (p.sources_merged.length === 1 && p.sources_merged[0] === "arxiv") arxivOnly.push(p);
    else others.push(p);
  }
  return [...others, ...arxivOnly];
}
