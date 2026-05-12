// Phase 40 (v1.4) — F3 cross-route query persistence.
//
// User types a query in /lit, switches to /hypothesis, the query is
// gone. This store keeps the most recent query per project so the
// hypothesis claim-form can pre-fill the textarea when the user
// arrives with an empty claim. One-way in v1.4 (lit → hypothesis);
// v1.5+ may extend to bidirectional sync.
//
// Decisions (locked in NEXT_SESSION_v1_4 §10.3):
//   - localStorage, not URL params (avoids route-coupling logic).
//   - Per-project key.
//   - Pre-fill only when the textarea is empty — never overwrite
//     user-typed content. The affordance caption shows the user where
//     the value came from.
//   - SSR-safe: every accessor checks `typeof window` first.

const PREFIX = "organon:cross-route-query:";

export type CrossRouteQuery = {
  query: string;
  last_route: string;
  updated_at: string;
};

function key(project: string): string {
  return `${PREFIX}${project}`;
}

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function getCrossRouteQuery(project: string): CrossRouteQuery | null {
  const s = storage();
  if (!s) return null;
  try {
    const raw = s.getItem(key(project));
    if (!raw) return null;
    const obj = JSON.parse(raw) as Partial<CrossRouteQuery>;
    if (typeof obj?.query !== "string") return null;
    if (typeof obj?.last_route !== "string") return null;
    return {
      query: obj.query,
      last_route: obj.last_route,
      updated_at: typeof obj.updated_at === "string" ? obj.updated_at : new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

export function setCrossRouteQuery(
  project: string,
  query: string,
  fromRoute: string,
): void {
  const s = storage();
  if (!s) return;
  try {
    const trimmed = query.trim();
    if (!trimmed) {
      s.removeItem(key(project));
      return;
    }
    const payload: CrossRouteQuery = {
      query: trimmed,
      last_route: fromRoute,
      updated_at: new Date().toISOString(),
    };
    s.setItem(key(project), JSON.stringify(payload));
  } catch {
    // quota / private-mode — degrade silently
  }
}

export function clearCrossRouteQuery(project: string): void {
  const s = storage();
  if (!s) return;
  try {
    s.removeItem(key(project));
  } catch { /* ignore */ }
}
