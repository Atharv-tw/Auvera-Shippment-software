import { useEffect, useState } from "react";

/** useState that survives a remount and a reload.
 *
 * The per-PO page remounts whenever you switch line tabs, so anything the user
 * has arranged — which sections are open, which fields they pinned to Quick
 * view — has to outlive that, and outlive a page reload too.
 *
 * The stored value is read **during** the first render, not in an effect
 * afterwards. Reading it afterwards means the first paint shows the default and
 * the second shows the truth, which is visible as a flash of open sections on
 * every tab switch. The trade-off: a component that renders this state on the
 * server would hydrate to different markup. The callers here render only after
 * a client-side fetch resolves, so the server never paints it.
 */

function read<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback; // unreadable or corrupt storage must not take the page down
  }
}

export function usePersistentState<T>(key: string, initial: T) {
  // The key is part of the state, because it changes: it carries the user id,
  // which is not known on the first render. When it changes the stored value
  // for the new key is adopted, rather than the previous user's value being
  // written into the new user's slot.
  const [state, setState] = useState<{ key: string; value: T }>(() => ({
    key,
    value: read(key, initial),
  }));

  if (state.key !== key) {
    // Re-deriving state during render is React's documented way to respond to a
    // changed input without an extra commit - an effect here would paint the
    // stale value first, which is the flash this hook exists to avoid.
    setState({ key, value: read(key, initial) });
  }

  useEffect(() => {
    if (state.key !== key) return; // mid-switch; the render above will settle it
    try {
      window.localStorage.setItem(key, JSON.stringify(state.value));
    } catch {
      /* quota or private mode - the preference just is not remembered */
    }
  }, [key, state]);

  const setValue = (next: T | ((current: T) => T)) =>
    setState((current) => ({
      key: current.key,
      value: typeof next === "function" ? (next as (c: T) => T)(current.value) : next,
    }));

  return [state.value, setValue] as const;
}
