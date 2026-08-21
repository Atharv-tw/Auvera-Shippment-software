import { useEffect, useState } from "react";

/** useState that survives a remount and a reload.
 *
 * The per-PO card is keyed on the tracker row id, so switching line tabs
 * remounts it and any local state dies with it. Anything the user has arranged
 * - which sections are open, which fields they pinned to Quick View - has to
 * outlive that, and outlive a page reload too.
 *
 * Reads happen after mount rather than during the first render: localStorage
 * does not exist on the server, and seeding state from it directly would make
 * the server and client markup disagree.
 */
export function usePersistentState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(initial);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(key);
      if (raw !== null) setValue(JSON.parse(raw) as T);
    } catch {
      /* unreadable or corrupt - fall back to the initial value */
    }
    setHydrated(true);
  }, [key]);

  useEffect(() => {
    if (!hydrated) return; // never write the initial value over a stored one
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* quota or private mode - the preference just is not remembered */
    }
  }, [key, value, hydrated]);

  return [value, setValue] as const;
}
