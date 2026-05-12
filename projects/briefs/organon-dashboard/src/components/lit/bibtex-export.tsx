"use client";

import type { PaperArtifact } from "@/lib/artifacts/types";
import { libraryToBibtex } from "@/lib/lit/bibtex";

export type BibtexExportProps = {
  papers: PaperArtifact[];
  filename: string;
};

export function BibtexExport({ papers, filename }: BibtexExportProps) {
  const handleExport = () => {
    if (papers.length === 0) return;
    const bibtex = libraryToBibtex(papers);
    const blob = new Blob([bibtex], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <button
      onClick={handleExport}
      disabled={papers.length === 0}
      className="w-full px-3 py-2 border border-border rounded text-xs mono uppercase tracking-wider text-text-dim hover:text-accent hover:border-accent transition disabled:opacity-50 disabled:cursor-not-allowed"
    >
      Export BibTeX ({papers.length})
    </button>
  );
}
