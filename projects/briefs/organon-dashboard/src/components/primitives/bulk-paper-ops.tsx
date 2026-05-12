"use client";

/**
 * Phase 39 (v1.4) — F2 shared BulkPaperOps primitive.
 *
 * The ALL/NONE/INVERT/DELETE row originally inlined into Phase 38's
 * library-panel. Lifted here so library-panel, the linked-papers
 * picker (paper-picker), and the chat-panel selected-files chips
 * render the same affordance with consistent `data-action` hooks.
 *
 * Callback-only — caller owns the click handlers + selection state.
 * Distinct from `BulkSelect` (component-owned, generic over T): this
 * primitive is pre-styled for paper-list affordances and exposes a
 * 4th DELETE button that's conditional on the caller supplying
 * `onDelete`. Surfaces without "delete from data store" semantics
 * (e.g. chat-panel chips, where DELETE = deselect, not delete) just
 * omit the prop.
 *
 * Tests pin the four data-action hooks on the DOM:
 *   data-action="bulk-all"
 *   data-action="bulk-none"
 *   data-action="bulk-invert"
 *   data-action="bulk-delete"   (conditional)
 */

export type BulkPaperOpsProps = {
  onAll: () => void;
  onNone: () => void;
  onInvert: () => void;
  onDelete?: () => void;
  selectedCount: number;
  totalCount: number;
  /** Optional className appended to the wrapper. */
  className?: string;
  /** Optional label for the count chip. Defaults to "papers". */
  label?: string;
  /** Optional title shown on the DELETE button when supplied. */
  deleteTitle?: string;
};

const BTN_CLS =
  "mono text-[10px] uppercase tracking-wider px-2 py-1 border border-border rounded text-text-muted hover:text-text hover:border-text-dim disabled:opacity-40";

export function BulkPaperOps({
  onAll,
  onNone,
  onInvert,
  onDelete,
  selectedCount,
  totalCount,
  className,
  label = "papers",
  deleteTitle = "Delete selected",
}: BulkPaperOpsProps) {
  return (
    <div
      data-bulk-paper-ops
      className={`flex items-center gap-1 ${className ?? ""}`}
    >
      <button
        type="button"
        data-action="bulk-all"
        onClick={onAll}
        disabled={totalCount === 0 || selectedCount === totalCount}
        className={BTN_CLS}
      >
        ALL
      </button>
      <button
        type="button"
        data-action="bulk-none"
        onClick={onNone}
        disabled={selectedCount === 0}
        className={BTN_CLS}
      >
        NONE
      </button>
      <button
        type="button"
        data-action="bulk-invert"
        onClick={onInvert}
        disabled={totalCount === 0}
        className={BTN_CLS}
      >
        INVERT
      </button>
      {onDelete && (
        <button
          type="button"
          data-action="bulk-delete"
          onClick={onDelete}
          disabled={selectedCount === 0}
          title={deleteTitle}
          className={`${BTN_CLS} hover:text-danger hover:border-danger ml-auto`}
        >
          DELETE
        </button>
      )}
      <span
        className="mono text-[10px] tracking-wider text-text-muted"
        data-bulk-paper-count
        data-selected={selectedCount}
        data-total={totalCount}
      >
        {selectedCount} of {totalCount} {label}
      </span>
    </div>
  );
}
