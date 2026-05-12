"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { useHotkeys } from "react-hotkeys-hook";
import type { TopbarProject } from "./topbar";
import type { SearchHit } from "@/lib/search";

type Skill = {
  name: string;
  category: string;
  description: string;
  slug: string;
};

type SkillGroup = {
  category: string;
  label: string;
  skills: Skill[];
};

const WORKSPACES: { href: string; label: string; phase?: string }[] = [
  { href: "/lit", label: "Literature" },
  { href: "/hypothesis", label: "Hypothesis" },
  { href: "/data", label: "Data" },
  { href: "/figures", label: "Figures" },
  { href: "/draft", label: "Draft" },
  { href: "/tools", label: "Tools" },
  { href: "/crons", label: "Crons" },
  { href: "/runs", label: "Runs" },
];

const DATA_ACTIONS: { label: string; query: string; href: string; tab?: "preview" | "stats" | "plots" }[] = [
  { label: "Go to Data · upload", query: "data upload file", href: "/data" },
  { label: "Run stat test", query: "data stat test picker", href: "/data", tab: "stats" },
  { label: "Generate plot", query: "data plot picker", href: "/data", tab: "plots" },
];

const FIGURES_ACTIONS: { label: string; query: string; href: string }[] = [
  { label: "Go to Figures", query: "figures generate", href: "/figures" },
  { label: "New figure (prompt)", query: "figures new prompt generate image", href: "/figures" },
  { label: "Edit current figure region", query: "figures edit region inpaint mask", href: "/figures" },
  { label: "Lock current figure + caption", query: "figures lock caption alt text", href: "/figures" },
];

const DRAFT_ACTIONS: { label: string; query: string; href: string }[] = [
  { label: "Go to Drafts", query: "draft manuscript list", href: "/draft" },
  { label: "New manuscript", query: "draft new manuscript create", href: "/draft" },
];

const HYPOTHESIS_ACTIONS: { label: string; query: string; href: string }[] = [
  { label: "New hypothesis", query: "hypothesis new claim", href: "/hypothesis" },
  {
    label: "Filter hypotheses · open",
    query: "hypothesis status open",
    href: "/hypothesis",
  },
  {
    label: "Filter hypotheses · synthesized",
    query: "hypothesis status synthesized",
    href: "/hypothesis",
  },
  {
    label: "Filter hypotheses · supported",
    query: "hypothesis status supported",
    href: "/hypothesis",
  },
  {
    label: "Filter hypotheses · refuted",
    query: "hypothesis status refuted",
    href: "/hypothesis",
  },
];

export type CommandPaletteProps = {
  open: boolean;
  onClose: () => void;
  projects: TopbarProject[];
  skillGroups: SkillGroup[];
  currentProject: string;
  onProjectChange: (slug: string) => void;
};

export function CommandPalette({
  open,
  onClose,
  projects,
  skillGroups,
  currentProject,
  onProjectChange,
}: CommandPaletteProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);

  // Esc closes
  useHotkeys("esc", () => open && onClose(), { enableOnFormTags: true }, [open]);

  // Debounced cross-corpus search via /api/search
  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    if (q.length < 2) { setHits([]); return; }
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/search?project=${encodeURIComponent(currentProject)}&q=${encodeURIComponent(q)}&limit=8`,
        );
        const json = await res.json();
        if (!cancelled && Array.isArray(json.results)) setHits(json.results);
      } catch { /* keep last good */ }
    }, 120);
    return () => { cancelled = true; clearTimeout(t); };
  }, [currentProject, open, query]);

  // Reset query when palette closes / project switches.
  useEffect(() => { if (!open) { setQuery(""); setHits([]); } }, [open]);
  useEffect(() => { setHits([]); }, [currentProject]);

  if (!open) return null;

  const navigate = (href: string) => {
    onClose();
    router.push(`${href}?project=${encodeURIComponent(currentProject)}`);
  };

  const switchProject = (slug: string) => {
    onClose();
    onProjectChange(slug);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-black/60"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <Command label="Command palette" loop shouldFilter>
          <Command.Input
            placeholder="Search papers, hypotheses, figures, sections, skills…"
            autoFocus
            value={query}
            onValueChange={setQuery}
          />
          <Command.List>
            <Command.Empty>No matches.</Command.Empty>

            {hits.length > 0 && (
              <Command.Group heading={`Search · ${hits.length} hits`}>
                {hits.map((h) => (
                  <Command.Item
                    key={`${h.type}:${h.id}`}
                    value={`hit ${h.type} ${h.id} ${h.title}`}
                    onSelect={() => {
                      onClose();
                      router.push(h.href);
                    }}
                  >
                    <span className="mono text-text-muted text-xs w-16">{h.type}</span>
                    <span className="truncate">{h.title}</span>
                    {h.subtitle && (
                      <span className="ml-auto text-text-muted text-xs truncate max-w-[35%]">{h.subtitle}</span>
                    )}
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            <Command.Group heading="Navigate">
              {WORKSPACES.map((w) => (
                <Command.Item
                  key={w.href}
                  value={`workspace ${w.label} ${w.href}`}
                  onSelect={() => navigate(w.href)}
                >
                  <span className="mono text-text-muted text-xs w-16">go</span>
                  <span>{w.label}</span>
                  {w.phase && (
                    <span className="ml-auto mono text-[10px] uppercase tracking-wider text-text-muted">
                      {w.phase}
                    </span>
                  )}
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Group heading="Data">
              {DATA_ACTIONS.map((a) => (
                <Command.Item
                  key={a.label}
                  value={a.query}
                  onSelect={() => {
                    onClose();
                    const sp = new URLSearchParams();
                    sp.set("project", currentProject);
                    if (a.tab) sp.set("tab", a.tab);
                    router.push(`${a.href}?${sp.toString()}`);
                  }}
                >
                  <span className="mono text-text-muted text-xs w-16">data</span>
                  <span>{a.label}</span>
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Group heading="Figures">
              {FIGURES_ACTIONS.map((a) => (
                <Command.Item
                  key={a.label}
                  value={a.query}
                  onSelect={() => {
                    onClose();
                    router.push(`${a.href}?project=${encodeURIComponent(currentProject)}`);
                  }}
                >
                  <span className="mono text-text-muted text-xs w-16">figs</span>
                  <span>{a.label}</span>
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Group heading="Draft">
              {DRAFT_ACTIONS.map((a) => (
                <Command.Item
                  key={a.label}
                  value={a.query}
                  onSelect={() => {
                    onClose();
                    router.push(`${a.href}?project=${encodeURIComponent(currentProject)}`);
                  }}
                >
                  <span className="mono text-text-muted text-xs w-16">draft</span>
                  <span>{a.label}</span>
                </Command.Item>
              ))}
            </Command.Group>

            <Command.Group heading="Hypothesis">
              {HYPOTHESIS_ACTIONS.map((a) => (
                <Command.Item
                  key={a.label}
                  value={a.query}
                  onSelect={() => {
                    onClose();
                    if (a.label.startsWith("Filter")) {
                      const status = a.label.split("·")[1].trim();
                      router.push(
                        `${a.href}?project=${encodeURIComponent(currentProject)}&status=${encodeURIComponent(status)}`,
                      );
                    } else {
                      router.push(`${a.href}?project=${encodeURIComponent(currentProject)}`);
                    }
                  }}
                >
                  <span className="mono text-text-muted text-xs w-16">hyp</span>
                  <span>{a.label}</span>
                </Command.Item>
              ))}
            </Command.Group>

            {projects.length > 1 && (
              <Command.Group heading="Switch project">
                {projects.map((p) => (
                  <Command.Item
                    key={p.slug}
                    value={`project ${p.name} ${p.slug}`}
                    onSelect={() => switchProject(p.slug)}
                  >
                    <span className="mono text-text-muted text-xs w-16">project</span>
                    <span>{p.name}</span>
                    {p.slug === currentProject && (
                      <span className="ml-auto text-text-muted text-xs">current</span>
                    )}
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            {skillGroups.flatMap((g) =>
              g.skills.length === 0 ? null : (
                <Command.Group key={g.category} heading={`Skills · ${g.label}`}>
                  {g.skills.map((s) => (
                    <Command.Item
                      key={s.name}
                      value={`skill ${s.name} ${s.description}`}
                      onSelect={() => navigate("/")}
                    >
                      <span className="mono text-text-muted text-xs w-16">skill</span>
                      <span>{s.name}</span>
                      <span className="ml-auto text-text-muted text-xs truncate max-w-[40%]">
                        {s.description.slice(0, 60)}
                      </span>
                    </Command.Item>
                  ))}
                </Command.Group>
              ),
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
