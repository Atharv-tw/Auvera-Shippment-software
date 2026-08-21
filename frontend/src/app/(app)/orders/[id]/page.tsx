"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, Badge, Spinner, ErrorNote } from "@/components/ui";
import { poLinePath } from "@/lib/routes";
import type { Order } from "@/lib/types";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-md border border-slate-100 bg-white p-2 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-[11px] text-slate-400 dark:text-slate-500">{label}</div>
      <div className="mt-0.5 text-sm text-slate-800 dark:text-slate-200">{value ?? "—"}</div>
    </div>
  );
}

export default function OrderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const order = useQuery({
    queryKey: ["order", id],
    queryFn: () => api<Order>(`/api/orders/${id}`),
  });

  if (order.isLoading) return <Spinner />;
  if (order.error) return <ErrorNote message={(order.error as Error).message} />;
  const o = order.data!;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">
          ← Dashboard
        </Link>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Order {o.order_number}</h1>
        <Badge color="blue">{o.is_confirmation ? "confirmation" : "order"}</Badge>
        <Link
          href={poLinePath(o.order_number ?? "")}
          className="ml-auto text-sm text-blue-600 hover:underline"
        >
          Open purchase order →
        </Link>
      </div>

      <Card title="Order details">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Field label="Supplier" value={o.supplier} />
          <Field label="Code" value={o.code} />
          <Field label="Country of Payment" value={o.country_of_payment} />
          <Field label="Payment Terms" value={o.payment_terms} />
          <Field label="Currency" value={o.currency} />
          <Field label="Terms of Delivery" value={o.terms_of_delivery} />
          <Field label="Port of Loading" value={o.port_of_loading} />
          <Field label="Source file" value={o.source_filename} />
        </div>
      </Card>

      <Card title={`Line items (${o.lines.length})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-2 pr-4">Article</th>
                <th className="py-2 pr-4">Description</th>
                <th className="py-2 pr-4">Colour</th>
                <th className="py-2 pr-4">Style</th>
                <th className="py-2 pr-4">TopUp</th>
                <th className="py-2 pr-4">Qty</th>
                <th className="py-2 pr-4">Price</th>
                <th className="py-2 pr-4">Total</th>
                <th className="py-2 pr-4">ETD</th>
              </tr>
            </thead>
            <tbody>
              {o.lines.map((l) => (
                <tr key={l.id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-2 pr-4">{l.article ?? "—"}</td>
                  <td className="py-2 pr-4">{l.description}</td>
                  <td className="py-2 pr-4">{l.colour}</td>
                  <td className="py-2 pr-4">{l.style_no}</td>
                  <td className="py-2 pr-4">{l.topup ?? "—"}</td>
                  <td className="py-2 pr-4">{l.quantity ?? "—"}</td>
                  <td className="py-2 pr-4">{l.price ?? "—"}</td>
                  <td className="py-2 pr-4">{l.total_spent ?? "—"}</td>
                  <td className="py-2 pr-4">{l.etd ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
