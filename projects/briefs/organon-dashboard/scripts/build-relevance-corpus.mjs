#!/usr/bin/env node
/**
 * Phase 56 (v2.1) — A2: relevance corpus builder.
 *
 * Idempotent. Merges:
 *   1. The existing src/lib/lit/relevance-corpus.json (preserves any hand-
 *      tuned IDF values from earlier phases).
 *   2. tests/fixtures/biomedical-tokens.txt — one token per line, blank
 *      lines and `#` comments ignored. Default IDF for new tokens is 1.4
 *      (between common ~1.0 fillers and specialty ~2.0+ terms).
 *
 * Usage:
 *   node scripts/build-relevance-corpus.mjs
 *
 * Why a static asset, not embeddings: v2.1 keeps the scoreRelevance
 * interface stable so an embedding swap (v2.2+) is local. The IDF table
 * is good enough for the common biomedical vocabulary; expansion here
 * brings ~190 → ≥ 1500 tokens to fix the 0.00 score collapse on
 * unfamiliar query terms.
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

const CORPUS_PATH = join(ROOT, "src/lib/lit/relevance-corpus.json");
const FIXTURE_PATH = join(ROOT, "tests/fixtures/biomedical-tokens.txt");

const DEFAULT_NEW_IDF = 1.4;

function loadJson(path) {
  if (!existsSync(path)) return { total_docs: 50000, tokens: {} };
  return JSON.parse(readFileSync(path, "utf8"));
}

function loadFixture(path) {
  if (!existsSync(path)) {
    console.error(`fixture not found: ${path}`);
    process.exit(1);
  }
  const lines = readFileSync(path, "utf8").split(/\r?\n/);
  const out = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith("#")) continue;
    // Lower-case + alnum-only to match the tokenizer's normalisation.
    const norm = line.toLowerCase().replace(/[^a-z0-9]+/g, "");
    if (norm.length > 1) out.push(norm);
  }
  return out;
}

function main() {
  const corpus = loadJson(CORPUS_PATH);
  const tokens = corpus.tokens ?? {};
  const fixture = loadFixture(FIXTURE_PATH);

  let added = 0;
  for (const t of fixture) {
    if (!(t in tokens)) {
      tokens[t] = DEFAULT_NEW_IDF;
      added += 1;
    }
  }

  // Sort tokens alphabetically so diffs are readable.
  const sorted = Object.keys(tokens)
    .sort()
    .reduce((acc, k) => {
      acc[k] = tokens[k];
      return acc;
    }, {});

  const next = {
    total_docs: corpus.total_docs ?? 50000,
    tokens: sorted,
  };

  writeFileSync(CORPUS_PATH, JSON.stringify(next, null, 2) + "\n");
  console.log(
    `corpus: ${Object.keys(tokens).length} tokens (added ${added} from fixture)`,
  );
}

main();
