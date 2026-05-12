"use client";

import { useMemo } from "react";
import type {
  FigureArtifact,
  HypothesisArtifact,
  PaperArtifact,
} from "@/lib/artifacts/types";
import type { ManuscriptMeta } from "@/lib/draft/store";
import type { DatasetLite } from "./source-linkage-panel";

/**
 * Phase 53 (v2.0) — Read-only citation graph.
 *
 * Renders the manuscript as a hub with one leaf per linked artifact
 * (papers + hypotheses + figures + datasets). Pure SVG, no external
 * deps. Layout: leaves are spread on a single circle around the hub
 * with kind-specific colours so the eye can scan composition at a
 * glance. Hover-title shows the leaf's primary label; click does not
 * navigate (read-only by design — drilldown lives in the linkage panel).
 *
 * Cap: at most MAX_LEAVES are rendered; overflow surfaces as a "+N
 * more" pill to keep the SVG readable for densely-linked manuscripts.
 */

const MAX_LEAVES = 24;
const VIEWBOX_W = 520;
const VIEWBOX_H = 360;
const HUB_X = VIEWBOX_W / 2;
const HUB_Y = VIEWBOX_H / 2;
const RADIUS = 130;

type Leaf = {
  id: string;
  kind: "paper" | "hypothesis" | "figure" | "dataset";
  label: string;
};

const KIND_COLOR: Record<Leaf["kind"], string> = {
  paper: "#7aa2f7",
  hypothesis: "#bb9af7",
  figure: "#9ece6a",
  dataset: "#e0af68",
};

export type CitationGraphProps = {
  manuscript: ManuscriptMeta;
  hypotheses: HypothesisArtifact[];
  library: PaperArtifact[];
  figures: FigureArtifact[];
  datasets: DatasetLite[];
};

function truncate(s: string, n = 28): string {
  if (s.length <= n) return s;
  return s.slice(0, n - 1) + "…";
}

export function CitationGraph(props: CitationGraphProps) {
  const { manuscript, hypotheses, library, figures, datasets } = props;

  const leaves = useMemo<Leaf[]>(() => {
    const out: Leaf[] = [];
    const paperIds = manuscript.linked_paper_ids ?? [];
    const hypIds = manuscript.linked_hypothesis_ids ?? [];
    const figIds = manuscript.linked_figure_ids ?? [];
    const dsIds = manuscript.linked_dataset_ids ?? [];

    const libIndex = new Map(library.map((p) => [p.id, p]));
    const hypIndex = new Map(hypotheses.map((h) => [h.id, h]));
    const figIndex = new Map(figures.map((f) => [f.id, f]));
    const dsIndex = new Map(datasets.map((d) => [d.id, d]));

    for (const id of paperIds) {
      const p = libIndex.get(id);
      out.push({ id, kind: "paper", label: p?.title ?? id });
    }
    for (const id of hypIds) {
      const h = hypIndex.get(id);
      out.push({ id, kind: "hypothesis", label: h?.claim_short ?? h?.claim ?? id });
    }
    for (const id of figIds) {
      const f = figIndex.get(id);
      out.push({ id, kind: "figure", label: f?.caption ?? id });
    }
    for (const id of dsIds) {
      const d = dsIndex.get(id);
      out.push({ id, kind: "dataset", label: d?.filename ?? id });
    }
    return out;
  }, [manuscript, hypotheses, library, figures, datasets]);

  const visible = leaves.slice(0, MAX_LEAVES);
  const overflow = leaves.length - visible.length;

  const positioned = visible.map((leaf, i) => {
    const angle = (2 * Math.PI * i) / Math.max(visible.length, 1);
    return {
      ...leaf,
      x: HUB_X + RADIUS * Math.cos(angle),
      y: HUB_Y + RADIUS * Math.sin(angle),
    };
  });

  return (
    <div
      data-citation-graph
      className="border border-border-dim rounded bg-bg-elev p-3"
    >
      <div className="mono text-[10px] uppercase tracking-[0.2em] text-text-muted mb-2 flex items-center justify-between">
        <span>Citation graph ({leaves.length} linked)</span>
        <span className="flex items-center gap-3">
          {(["paper", "hypothesis", "figure", "dataset"] as Leaf["kind"][]).map((k) => (
            <span key={k} className="flex items-center gap-1">
              <span
                aria-hidden="true"
                style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: "9999px",
                  background: KIND_COLOR[k],
                }}
              />
              {k}
            </span>
          ))}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
        role="img"
        aria-label="Citation graph"
        className="w-full h-auto"
      >
        {positioned.map((leaf) => (
          <line
            key={`edge-${leaf.kind}-${leaf.id}`}
            x1={HUB_X}
            y1={HUB_Y}
            x2={leaf.x}
            y2={leaf.y}
            stroke="rgb(85, 95, 110)"
            strokeWidth={1}
            opacity={0.6}
          />
        ))}
        {/* Hub */}
        <g>
          <circle cx={HUB_X} cy={HUB_Y} r={28} fill="#414868" stroke="#7dcfff" strokeWidth={1.5} />
          <text
            x={HUB_X}
            y={HUB_Y + 4}
            textAnchor="middle"
            fontSize={11}
            fill="#c0caf5"
            fontFamily="ui-monospace, monospace"
          >
            <title>{manuscript.title}</title>
            {truncate(manuscript.title, 14)}
          </text>
        </g>
        {/* Leaves */}
        {positioned.map((leaf) => (
          <g key={`leaf-${leaf.kind}-${leaf.id}`}>
            <circle
              cx={leaf.x}
              cy={leaf.y}
              r={9}
              fill={KIND_COLOR[leaf.kind]}
              stroke="#1a1b26"
              strokeWidth={1}
            />
            <text
              x={leaf.x}
              y={leaf.y + 22}
              textAnchor="middle"
              fontSize={9}
              fill="#a9b1d6"
              fontFamily="ui-monospace, monospace"
            >
              <title>{leaf.label}</title>
              {truncate(leaf.label, 18)}
            </text>
          </g>
        ))}
        {overflow > 0 && (
          <text
            x={VIEWBOX_W - 12}
            y={VIEWBOX_H - 12}
            textAnchor="end"
            fontSize={10}
            fill="#7aa2f7"
            fontFamily="ui-monospace, monospace"
          >
            +{overflow} more not shown
          </text>
        )}
      </svg>
    </div>
  );
}
