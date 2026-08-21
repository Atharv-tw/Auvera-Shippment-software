import { useEffect, useState } from "react";

/** The value, but only after it has stopped changing for `delay` ms.
 *
 * Search boxes that hit the API need this: without it every keystroke is a
 * request. Client-side filters do not - they are free, so debouncing them only
 * adds lag.
 */
export function useDebounced<T>(value: T, delay = 300): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return settled;
}
