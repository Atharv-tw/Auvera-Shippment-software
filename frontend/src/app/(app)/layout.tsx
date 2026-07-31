"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui";
import { ThemeToggle } from "@/components/ThemeToggle";
import { clsx } from "@/components/clsx";

const NAV = [
  { href: "/dashboard", label: "Dashboard", adminOnly: false },
  { href: "/tracker", label: "Shipment Tracker", adminOnly: false },
  { href: "/upload", label: "Upload Sheets", adminOnly: true },
  { href: "/manual", label: "Manual Entry", adminOnly: false },
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
          <div className="text-sm font-bold text-slate-900 dark:text-slate-100">
            Order &amp; Shipment Tracker
          </div>
          <div className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
            {user.name} · {user.role}
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 p-2">
          {NAV.filter((item) => !item.adminOnly || user.role === "admin").map((item) => (
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
