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
  canUpload,
  canEditOrderDetails,
  canViewCustomers,
} from "@/lib/permissions";

const NAV: { href: string; label: string; show: (r: Role) => boolean }[] = [
  { href: "/dashboard", label: "Dashboard", show: () => true },
  { href: "/tracker", label: "Shipment Tracker", show: canViewTracker },
  { href: "/upload", label: "Upload Sheets", show: canUpload },
  { href: "/manual", label: "Manual Entry", show: canEditOrderDetails },
  { href: "/customers", label: "Customers", show: canViewCustomers },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) return <Spinner />;

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="border-b border-slate-100 px-4 py-4 dark:border-slate-800">
          <div className="flex items-center gap-2.5">
            <Image
              src="/logo.png"
              alt="Auvera"
              width={28}
              height={28}
              className="h-7 w-7 rounded object-contain"
            />
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-bold text-slate-900 dark:text-slate-100">
                Auvera Studio
              </div>
              <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Apparel Sourcing
              </div>
            </div>
          </div>
          <div className="mt-2 truncate text-xs text-slate-500 dark:text-slate-400">
            {user.name} · {ROLE_LABELS[user.role] ?? user.role}
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 p-2">
          {NAV.filter((item) => item.show(user.role)).map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "block rounded-md px-3 py-2 text-sm",
                isActive(item.href)
                  ? "bg-blue-50 font-medium text-blue-700 dark:bg-blue-500/10 dark:text-blue-400"
                  : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="space-y-1 border-t border-slate-100 p-2 dark:border-slate-800">
          <ThemeToggle className="w-full justify-center" />
          <button
            onClick={logout}
            className="w-full rounded-md px-3 py-2 text-left text-sm text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6">{children}</main>
    </div>
  );
}
