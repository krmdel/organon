import Link from "next/link";

export function StubWorkspace({
  label,
  phase,
  description,
  currentProject,
}: {
  label: string;
  phase: string;
  description: string;
  currentProject: string;
}) {
  return (
    <div className="px-8 py-10 max-w-3xl">
      <div className="mono text-[11px] tracking-[0.2em] text-text-muted uppercase mb-2">
        {label}
      </div>
      <h1 className="text-2xl font-semibold mb-3">Coming in {phase}</h1>
      <p className="text-text-dim leading-relaxed mb-8">{description}</p>
      <Link
        href={`/lit?project=${encodeURIComponent(currentProject)}`}
        className="inline-block px-4 py-2 border border-border rounded text-sm hover:bg-bg-soft transition"
      >
        ← Back to Literature
      </Link>
    </div>
  );
}
