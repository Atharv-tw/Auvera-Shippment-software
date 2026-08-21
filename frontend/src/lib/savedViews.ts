import type { Chip } from "@/lib/fieldVocabulary";

/** A named tracker layout: which columns, which filters, which sort and pins.
 *
 * Kept in localStorage rather than a table. Views are per-user and need no
 * sharing to be useful, and the backend has no migration story cheap enough to
 * justify a table for it yet. Promoting this to the server is the right move
 * only when a view has to be shared - "the CEO sets the default everyone lands
 * on" - and the shape here is already what such a table would store.
 */
export type SavedView = {
  name: string;
  chips: Chip[];
  /** AG Grid column state: order, width, pinning, sort, visibility. */
  columnState: unknown[];
  filterModel: Record<string, unknown>;
  savedAt: string;
};

const KEY_PREFIX = "tracker-views:";

const storageKey = (userId: number | string) => `${KEY_PREFIX}${userId}`;

export function loadViews(userId: number | string): SavedView[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(storageKey(userId));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? (parsed as SavedView[]) : [];
  } catch {
    // corrupt or unreadable storage must not take the page down with it
    return [];
  }
}

function persist(userId: number | string, views: SavedView[]) {
  try {
    window.localStorage.setItem(storageKey(userId), JSON.stringify(views));
  } catch {
    /* quota or private mode - the view simply is not saved */
  }
}

/** Saving over an existing name replaces it, which is what "save" means to
 * someone who has just adjusted the view they are looking at. */
export function saveView(userId: number | string, view: SavedView): SavedView[] {
  const views = loadViews(userId).filter((v) => v.name !== view.name);
  const next = [...views, view].sort((a, b) => a.name.localeCompare(b.name));
  persist(userId, next);
  return next;
}

export function deleteView(userId: number | string, name: string): SavedView[] {
  const next = loadViews(userId).filter((v) => v.name !== name);
  persist(userId, next);
  return next;
}
