/**
 * Phase 2 lift — the canonical drawer lives in components/primitives/.
 * This file remains as a thin re-export so existing imports still resolve.
 */
export {
  PaperDetailDrawer as PaperDetail,
  type PaperDetailDrawerProps as PaperDetailProps,
} from "@/components/primitives/paper-detail-drawer";
