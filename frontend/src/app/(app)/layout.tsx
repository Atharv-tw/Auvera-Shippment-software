"use client";

import { useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui";
import { ThemeToggle } from "@/components/ThemeToggle";
import { clsx } from "@/components/clsx";
import type { Role } from "@/lib/types";
import {
  ROLE_LABELS,
  canViewTracker,
  canViewPos,
  canUpload,
  canCreateTrackerRow,
  canViewAudit,
  canPaste,
  canViewCustomers,
  canViewVendors,
  canViewReports,
  canManageUsers,
} from "@/lib/permissions";

type NavItem = { href: string; label: string; show: (r: Role) => boolean };

// Grouped so the sidebar reads as sections rather than one long list. The
// per-PO view sits above the tracker deliberately: it is the view most roles
// live in, and merchants only ever see that one.
const NAV: { heading: string | null; items: NavItem[] }[] = [
  {
    heading: null,
    items: [
      { href: "/dashboard", label: "Dashboard", show: () => true },
      { href: "/pos", label: "Purchase Orders", show: canViewPos },
      { href: "/tracker", label: "Shipment Tracker", show: canViewTracker },
    ],
  },
  {
    heading: "Data in",
    items: [
      { href: "/upload", label: "Upload Sheets", show: canUpload },
      { href: "/paste", label: "Paste PO Details", show: canPaste },
      { href: "/manual", label: "Manual PO Line", show: canCreateTrackerRow },
    ],
  },
  {
    heading: "Records",
    items: [
      { href: "/customers", label: "Customers", show: canViewCustomers },
      { href: "/vendors", label: "Vendors", show: canViewVendors },
      { href: "/reports", label: "Reports", show: canViewReports },
      { href: "/users", label: "Users", show: canManageUsers },
      { href: "/activity", label: "Sign-in Activity", show: canViewAudit },
    ],
  },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout, logoutEverywhere } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    // A pending account has no role and no access - it belongs on the waitlist,
    // never on an app page.
    else if (user.role === "pending") router.replace("/waitlist");
  }, [loading, user, router]);

  if (loading || !user || user.role === "pending") return <Spinner />;

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col bg-slate-900">
        <div className="border-b border-slate-700/50 px-4 py-4">
          <div className="flex items-center gap-2.5">
            <Image
              src="/logo.png"
              alt="Auvera"
              width={28}
              height={28}
              className="h-7 w-7 rounded object-contain"
            />
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-bold text-white">
                Auvera Studio
              </div>
              <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                Apparel Sourcing
              </div>
            </div>
          </div>
          <div className="mt-2 truncate text-xs text-slate-400">
            {user.name} · {ROLE_LABELS[user.role] ?? user.role}
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto p-2">
          {NAV.map((section) => {
            const items = section.items.filter((item) => item.show(user.role));
            if (items.length === 0) return null;
            return (
              <div key={section.heading ?? "main"} className="mb-3 space-y-0.5">
                {section.heading && (
                  <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {section.heading}
                  </div>
                )}
                {items.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={clsx(
                      "block rounded-md px-3 py-2 text-sm",
                      isActive(item.href)
                        ? "bg-blue-500/15 font-medium text-blue-400"
                        : "text-slate-300 hover:bg-slate-800 hover:text-white",
                    )}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="space-y-1 border-t border-slate-700/50 p-2">
          <ThemeToggle className="w-full justify-center" />
          <button
            onClick={logout}
            className="w-full rounded-md px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-800 hover:text-white"
          >
            Sign out
          </button>
          {/* For the shared-desktop case: signing out here leaves any other
              browser still signed in, which is the one thing people assume it
              does not do. */}
          <button
            onClick={() => {
              if (
                window.confirm(
                  "Sign out of every browser and device you are signed in on?",
                )
              )
                logoutEverywhere();
            }}
            className="w-full rounded-md px-3 py-2 text-left text-xs text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            Sign out everywhere
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6">{children}</main>
    </div>
  );
}
