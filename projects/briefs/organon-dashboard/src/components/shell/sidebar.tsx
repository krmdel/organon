"use client";

import Link from "next/link";
import { cn } from "@/lib/cn";

type WorkspaceLink = {
  href: string;
  label: string;
  badge?: string;
  active?: boolean;
};

export type SidebarProps = {
  /** Active workspace path, e.g. "/lit". Drives the highlighted link. */
  activePath: string;
  /** Project slug appended as ?project= on every link. */
  currentProject: string;
};

const LINKS: Omit<WorkspaceLink, "active">[] = [
  { href: "/lit", label: "Literature" },
  { href: "/hypothesis", label: "Hypothesis" },
  { href: "/data", label: "Data" },
  { href: "/figures", label: "Figures" },
  { href: "/draft", label: "Draft" },
  { href: "/tools", label: "Tools" },
  { href: "/crons", label: "Crons" },
  { href: "/runs", label: "Runs" },
];

export function Sidebar({ activePath, currentProject }: SidebarProps) {
  return (
    <aside className="w-56 shrink-0 border-r border-border-dim bg-bg-elev flex flex-col">
      <Link
        href={`/?project=${encodeURIComponent(currentProject)}`}
        className="px-5 py-5 border-b border-border-dim block hover:bg-bg-soft transition"
      >
        <div className="mono text-[11px] tracking-[0.2em] text-text-muted uppercase">Organon</div>
        <div className="mono text-base text-text mt-1">Dashboard</div>
      </Link>

      <nav className="flex-1 py-4">
        {LINKS.map((link) => {
          const isActive = activePath === link.href || activePath.startsWith(link.href + "/");
          return (
            <Link
              key={link.href}
              href={`${link.href}?project=${encodeURIComponent(currentProject)}`}
              className={cn(
                "flex items-center justify-between px-5 py-2 text-sm transition",
                isActive
                  ? "text-text bg-accent-faint border-l-2 border-accent -ml-[2px] pl-[18px]"
                  : "text-text-dim hover:text-text hover:bg-bg-soft",
              )}
            >
              <span>{link.label}</span>
              {link.badge && (
                <span className="mono text-[10px] uppercase tracking-wider text-text-muted">
                  {link.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4 border-t border-border-dim">
        <div className="mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
          Phase 6 · Tools / Crons / Runs · v1.0 candidate
        </div>
      </div>
    </aside>
  );
}
