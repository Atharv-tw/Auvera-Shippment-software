"use client";

import Link from "next/link";
import {
  Table,
  Upload,
  PencilLine,
  LayoutDashboard,
  ArrowRight,
  Ship,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui";

const FEATURES = [
  {
    title: "Shipment Tracker",
    desc: "One editable Excel-style grid for every order — buyer and factory columns in one place.",
    icon: Table,
  },
  {
    title: "Upload Sheets",
    desc: "Drop Customer and Vendor order workbooks; rows are matched and merged automatically.",
    icon: Upload,
  },
  {
    title: "Dashboard",
    desc: "See orders, vendor orders and tracker status at a glance.",
    icon: LayoutDashboard,
  },
  {
    title: "Manual Entry",
    desc: "Add or correct a tracker row by hand when a sheet isn't enough.",
    icon: PencilLine,
  },
];

export default function LandingPage() {
  const { user, loading } = useAuth();

  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      <header className="flex items-center justify-between border-b border-slate-200 px-6 py-4 dark:border-slate-800">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-slate-100">
          <Ship size={18} className="text-blue-600 dark:text-blue-400" />
          Order &amp; Shipment Tracker
        </div>
        <div className="flex items-center gap-2">
          {!loading && user ? (
            <Link href="/dashboard">
              <Button>
                Open app <ArrowRight size={16} />
              </Button>
            </Link>
          ) : (
            <Link href="/login">
              <Button>Login</Button>
            </Link>
          )}
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-4xl px-6 py-20 text-center sm:py-28">
          <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl dark:text-slate-100">
            Track every order from{" "}
            <span className="text-blue-600 dark:text-blue-400">
              PO to shipment
            </span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600 dark:text-slate-400">
            Ingest customer and vendor order paperwork into one central shipment
            tracker. No more juggling spreadsheets across email threads.
          </p>
          <div className="mt-9 flex items-center justify-center gap-3">
            {!loading && user ? (
              <Link href="/dashboard">
                <Button className="px-5 py-2.5 text-base">
                  Open app <ArrowRight size={18} />
                </Button>
              </Link>
            ) : (
              <Link href="/login">
                <Button className="px-5 py-2.5 text-base">
                  Login <ArrowRight size={18} />
                </Button>
              </Link>
            )}
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-6 pb-24">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <div
                  key={f.title}
                  className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
                >
                  <div className="rounded-lg bg-blue-50 p-2 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                    <Icon size={20} />
                  </div>
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-900 dark:text-slate-100">
                      {f.title}
                    </div>
                    <div className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                      {f.desc}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 px-6 py-6 text-center text-xs text-slate-400 dark:border-slate-800 dark:text-slate-500">
        Order &amp; Shipment Tracker
      </footer>
    </div>
  );
}
