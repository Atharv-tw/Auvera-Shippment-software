"use client";

import Link from "next/link";
import Image from "next/image";
import {
  Package,
  Ship,
  FileSpreadsheet,
  BarChart3,
  ArrowRight,
  Shield,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui";

const SERVICES = [
  {
    icon: Package,
    title: "Order Management",
    desc: "Ingest buyer and vendor order sheets into one unified system. Auto-detect, parse, and reconcile every line item.",
  },
  {
    icon: Ship,
    title: "Shipment Tracking",
    desc: "56-column tracker covering booking, vessel, container, BL, and documentation — all in a single editable grid.",
  },
  {
    icon: FileSpreadsheet,
    title: "Smart Upload",
    desc: "Drag and drop Customer and Vendor workbooks. Rows are matched by PO, style, and colour automatically.",
  },
  {
    icon: BarChart3,
    title: "Full Visibility",
    desc: "Dashboard with order counts, tracker status, reconciliation health, and an auditable change trail.",
  },
];

const STATS = [
  { label: "Order Lines Tracked", value: "56+" },
  { label: "Tracker Columns", value: "A\u2013BD" },
  { label: "Payment Instruments", value: "LC / TT / DA / DP" },
  { label: "Role-Based Access", value: "4 Roles" },
];

export default function LandingPage() {
  const { user, loading } = useAuth();

  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/80">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-3">
            <Image
              src="/logo.png"
              alt="Auvera Studio Limited"
              width={36}
              height={36}
              className="h-9 w-9 rounded-md object-contain"
              priority
            />
            <div className="leading-tight">
              <div className="text-sm font-bold tracking-tight text-slate-900 dark:text-slate-50">
                Auvera Studio Limited
              </div>
              <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400 dark:text-slate-500">
                Apparel Sourcing
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {!loading && user ? (
              <Link href="/dashboard">
                <Button>
                  Dashboard <ArrowRight size={16} />
                </Button>
              </Link>
            ) : (
              <>
                <Link href="/login">
                  <Button variant="ghost">Sign in</Button>
                </Link>
                <Link href="/login">
                  <Button>
                    Get Started <ArrowRight size={16} />
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.03] dark:opacity-[0.05]"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)",
              backgroundSize: "32px 32px",
            }}
          />

          <div className="relative mx-auto max-w-6xl px-6 pb-20 pt-20 sm:pt-28 lg:pt-32">
            <div className="mx-auto max-w-3xl text-center">
              <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-blue-700 dark:border-blue-800 dark:bg-blue-500/10 dark:text-blue-400">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-600 dark:bg-blue-400" />
                Apparel Sourcing Platform
              </div>

              <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl lg:text-6xl dark:text-slate-50">
                From PO to{" "}
                <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent dark:from-blue-400 dark:to-indigo-400">
                  shipment
                </span>
                ,<br className="hidden sm:block" /> managed in one place
              </h1>

              <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-slate-600 dark:text-slate-400">
                Auvera Studio Limited manages the full apparel sourcing lifecycle
                &mdash; from purchase order ingestion through factory coordination
                to final shipment documentation. One platform, every detail.
              </p>

              <div className="mt-9 flex items-center justify-center gap-3">
                {!loading && user ? (
                  <Link href="/dashboard">
                    <Button className="px-6 py-3 text-base">
                      Open Dashboard <ArrowRight size={18} />
                    </Button>
                  </Link>
                ) : (
                  <Link href="/login">
                    <Button className="px-6 py-3 text-base">
                      Sign in to Tracker <ArrowRight size={18} />
                    </Button>
                  </Link>
                )}
              </div>
            </div>

            <div className="mx-auto mt-16 grid max-w-3xl grid-cols-2 gap-4 sm:grid-cols-4">
              {STATS.map((s) => (
                <div
                  key={s.label}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-4 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900"
                >
                  <div className="text-xl font-bold text-slate-900 dark:text-slate-50">
                    {s.value}
                  </div>
                  <div className="mt-0.5 text-[11px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">
                    {s.label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Services */}
        <section className="border-t border-slate-100 bg-slate-50/50 dark:border-slate-800/50 dark:bg-slate-900/30">
          <div className="mx-auto max-w-6xl px-6 py-20 sm:py-24">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl dark:text-slate-50">
                Everything you need to run apparel logistics
              </h2>
              <p className="mt-3 text-slate-500 dark:text-slate-400">
                Built specifically for garment buying houses managing
                buyer&ndash;factory&ndash;shipping workflows.
              </p>
            </div>

            <div className="mx-auto mt-12 grid max-w-4xl gap-5 sm:grid-cols-2">
              {SERVICES.map((s) => {
                const Icon = s.icon;
                return (
                  <div
                    key={s.title}
                    className="group rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
                  >
                    <div className="mb-4 inline-flex rounded-lg bg-blue-50 p-2.5 text-blue-600 transition group-hover:bg-blue-600 group-hover:text-white dark:bg-blue-500/10 dark:text-blue-400 dark:group-hover:bg-blue-600 dark:group-hover:text-white">
                      <Icon size={20} />
                    </div>
                    <h3 className="font-semibold text-slate-900 dark:text-slate-50">
                      {s.title}
                    </h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
                      {s.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* How It Works */}
        <section className="border-t border-slate-200 dark:border-slate-800">
          <div className="mx-auto max-w-6xl px-6 py-20 sm:py-24">
            <div className="mx-auto max-w-2xl text-center">
              <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl dark:text-slate-50">
                How it works
              </h2>
              <p className="mt-3 text-slate-500 dark:text-slate-400">
                Three steps from paperwork to a fully tracked shipment.
              </p>
            </div>

            <div className="mx-auto mt-14 grid max-w-4xl gap-8 sm:grid-cols-3">
              {[
                {
                  step: "01",
                  title: "Upload Sheets",
                  desc: "Drop in Customer Order and Vendor Order Excel workbooks. The system auto-detects the type and parses every line item.",
                },
                {
                  step: "02",
                  title: "Reconcile Orders",
                  desc: "Buyer and factory data are merged into tracker rows keyed by PO, style, and colour \u2014 prices, quantities, and specs aligned.",
                },
                {
                  step: "03",
                  title: "Track & Ship",
                  desc: "The shipping manager fills in booking, container, vessel, BL, and docs. The CEO reviews the audit trail. Everyone stays aligned.",
                },
              ].map((item) => (
                <div key={item.step} className="text-center">
                  <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border-2 border-blue-200 text-sm font-bold text-blue-600 dark:border-blue-800 dark:text-blue-400">
                    {item.step}
                  </div>
                  <h3 className="font-semibold text-slate-900 dark:text-slate-50">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Roles & Security */}
        <section className="border-t border-slate-100 bg-slate-50/50 dark:border-slate-800/50 dark:bg-slate-900/30">
          <div className="mx-auto max-w-6xl px-6 py-20 sm:py-24">
            <div className="mx-auto max-w-4xl">
              <div className="grid items-center gap-10 sm:grid-cols-2">
                <div>
                  <div className="mb-4 inline-flex rounded-lg bg-blue-50 p-2.5 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                    <Shield size={20} />
                  </div>
                  <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl dark:text-slate-50">
                    Role-based access for every team member
                  </h2>
                  <p className="mt-3 text-slate-500 dark:text-slate-400">
                    Four roles, each with precisely scoped permissions. Every field
                    change is logged in a per-field audit trail.
                  </p>

                  <ul className="mt-6 space-y-3">
                    {[
                      "Admin \u2014 full access to everything",
                      "CEO \u2014 edits order details, views audit trail",
                      "Shipping Manager \u2014 edits operational tracker data",
                      "Merchant \u2014 uploads and views orders",
                    ].map((item) => (
                      <li
                        key={item}
                        className="flex items-start gap-2.5 text-sm text-slate-600 dark:text-slate-400"
                      >
                        <CheckCircle2
                          size={16}
                          className="mt-0.5 shrink-0 text-blue-600 dark:text-blue-400"
                        />
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                  <div className="space-y-4">
                    {[
                      {
                        role: "Admin",
                        access: "Full Access",
                        color: "bg-red-50 text-red-700 ring-red-200 dark:bg-red-500/10 dark:text-red-400 dark:ring-red-500/30",
                      },
                      {
                        role: "CEO",
                        access: "Order Details + Audit",
                        color: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:ring-amber-500/30",
                      },
                      {
                        role: "Shipping Manager",
                        access: "Operational Data",
                        color: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-500/30",
                      },
                      {
                        role: "Merchant",
                        access: "Upload + View Orders",
                        color: "bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-500/10 dark:text-blue-400 dark:ring-blue-500/30",
                      },
                    ].map((r) => (
                      <div
                        key={r.role}
                        className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-3 dark:border-slate-800"
                      >
                        <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                          {r.role}
                        </span>
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${r.color}`}
                        >
                          {r.access}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="border-t border-slate-200 dark:border-slate-800">
          <div className="mx-auto max-w-6xl px-6 py-20 text-center sm:py-24">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl dark:text-slate-50">
              Ready to streamline your shipments?
            </h2>
            <p className="mx-auto mt-3 max-w-md text-slate-500 dark:text-slate-400">
              Sign in to access the Order &amp; Shipment Tracker.
            </p>
            <div className="mt-8">
              {!loading && user ? (
                <Link href="/dashboard">
                  <Button className="px-6 py-3 text-base">
                    Go to Dashboard <ArrowRight size={18} />
                  </Button>
                </Link>
              ) : (
                <Link href="/login">
                  <Button className="px-6 py-3 text-base">
                    Sign in <ArrowRight size={18} />
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 dark:border-slate-800">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
          <div className="flex items-center gap-2">
            <Image
              src="/logo.png"
              alt="Auvera Studio Limited"
              width={20}
              height={20}
              className="h-5 w-5 rounded object-contain"
            />
            <span className="text-xs text-slate-400 dark:text-slate-500">
              &copy; {new Date().getFullYear()} Auvera Studio Limited
            </span>
          </div>
          <span className="text-xs text-slate-400 dark:text-slate-500">
            Apparel Sourcing &amp; Shipment Management
          </span>
        </div>
      </footer>
    </div>
  );
}
