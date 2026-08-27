"use client";

import { useEffect, useState } from "react";

/** This tracker is a wide, dense, keyboard-and-mouse tool - the 56-column grid,
 * paste, and bulk edit are unusable on a phone. Rather than ship a broken small
 * screen, the whole site is blocked on phones and asks for a desktop instead.
 *
 * Phones only: tablets and laptops pass. Detection is user-agent first, with a
 * physical-screen fallback for phones that spoof a desktop UA. The short side of
 * the screen is used so rotating the phone does not slip past the check. */
function isPhone(): boolean {
  if (typeof window === "undefined") return false;
  const ua = navigator.userAgent || "";
  const uaPhone =
    /iPhone|iPod|Android.*Mobile|Windows Phone|BlackBerry|Opera Mini|IEMobile/i.test(ua);
  const shortSide = Math.min(window.screen?.width ?? 9999, window.screen?.height ?? 9999);
  const coarse = window.matchMedia?.("(pointer: coarse)").matches ?? false;
  return uaPhone || (coarse && shortSide < 500);
}

export function MobileGate({ children }: { children: React.ReactNode }) {
  // Assume desktop for the first paint so laptops never flash the notice; a
  // phone briefly sees the app, then swaps to the notice on mount. It cannot
  // use the app anyway, so the flash is harmless.
  const [phone, setPhone] = useState(false);

  useEffect(() => {
    const check = () => setPhone(isPhone());
    check();
    window.addEventListener("resize", check);
    window.addEventListener("orientationchange", check);
    return () => {
      window.removeEventListener("resize", check);
      window.removeEventListener("orientationchange", check);
    };
  }, []);

  if (!phone) return <>{children}</>;

  return (
    <main className="flex min-h-full flex-col items-center justify-center gap-4 px-6 py-12 text-center">
      <div
        aria-hidden
        className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-200 text-3xl dark:bg-slate-800"
      >
        🖥️
      </div>
      <h1 className="text-xl font-semibold">Please use a desktop</h1>
      <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400">
        The Auvera Studio tracker isn&apos;t available on phones. Open it on a
        desktop or laptop to view and edit the shipment tracker.
      </p>
    </main>
  );
}
