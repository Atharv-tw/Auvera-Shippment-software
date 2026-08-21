"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, Input, Spinner, ErrorNote } from "@/components/ui";
import { canManageVendors, canViewVendors } from "@/lib/permissions";
import type { Vendor } from "@/lib/types";

type VendorForm = Omit<Vendor, "id" | "created_at">;

const EMPTY: VendorForm = {
  name: "",
  address: "",
  vat_number: "",
  code: "",
  country: "",
  factory_town: "",
  port_of_loading: "",
  payment_terms: "",
  terms_of_delivery: "",
  currency: "",
};

const FIELDS: { key: keyof VendorForm; label: string; placeholder: string }[] = [
  { key: "name", label: "Factory Name", placeholder: "e.g. CRIMSON" },
  { key: "address", label: "Address", placeholder: "Street, city, postcode" },
  { key: "vat_number", label: "VAT / Tax Number", placeholder: "e.g. 27AAACR1234M1ZX" },
  { key: "code", label: "Code", placeholder: "e.g. SZ" },
  { key: "country", label: "Country", placeholder: "e.g. India" },
  { key: "factory_town", label: "Factory Town", placeholder: "e.g. Mumbai" },
  { key: "port_of_loading", label: "Port of Loading", placeholder: "e.g. Nhava Sheva" },
  { key: "payment_terms", label: "Payment Terms", placeholder: "e.g. 100%TT 30 DAYS" },
  { key: "terms_of_delivery", label: "Terms of Delivery", placeholder: "e.g. FOB(China,India)" },
  { key: "currency", label: "Currency", placeholder: "e.g. GBP" },
];

export default function VendorsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const canManage = !!user && canManageVendors(user.role);
  const allowed = !!user && canViewVendors(user.role);

  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<VendorForm>(EMPTY);

  const vendors = useQuery<Vendor[]>({
    queryKey: ["vendors", search],
    queryFn: () =>
      api<Vendor[]>(`/api/vendors${search ? `?search=${encodeURIComponent(search)}` : ""}`),
    enabled: allowed,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["vendors"] });
    resetForm();
  };

  const createMutation = useMutation({
    mutationFn: (data: VendorForm) =>
      api<Vendor>("/api/vendors", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: invalidate,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: VendorForm & { id: number }) =>
      api<Vendor>(`/api/vendors/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/vendors/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["vendors"] }),
  });

  function resetForm() {
    setShowForm(false);
    setEditingId(null);
    setForm(EMPTY);
  }

  function startEdit(v: Vendor) {
    setEditingId(v.id);
    setForm(
      Object.fromEntries(
        FIELDS.map((f) => [f.key, v[f.key] ?? ""]),
      ) as unknown as VendorForm,
    );
    setShowForm(true);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (editingId) updateMutation.mutate({ id: editingId, ...form });
    else createMutation.mutate(form);
  }

  if (user && !allowed)
    return <ErrorNote message="Your role does not have access to vendors." />;
  if (vendors.isLoading) return <Spinner />;

  const mutationError =
    createMutation.error || updateMutation.error || deleteMutation.error;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Vendors</h1>
          <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
            Factories. New ones appear here automatically when a vendor sheet is uploaded.
          </p>
        </div>
        {canManage && (
          <Button
            onClick={() => {
              resetForm();
              setShowForm(!showForm);
            }}
          >
            {showForm ? "Cancel" : "Add vendor"}
          </Button>
        )}
      </div>

      {vendors.error && <ErrorNote message={(vendors.error as Error).message} />}
      {mutationError && <ErrorNote message={(mutationError as Error).message} />}

      {showForm && (
        <Card title={editingId ? "Edit Vendor" : "New Vendor"}>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {FIELDS.map((f) => (
                <div key={f.key}>
                  <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                    {f.label}
                  </label>
                  <Input
                    required={f.key === "name"}
                    value={form[f.key] ?? ""}
                    onChange={(e) => setForm((s) => ({ ...s, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                  />
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {editingId ? "Save changes" : "Create vendor"}
              </Button>
              <Button variant="secondary" type="button" onClick={resetForm}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card
        title={`All Vendors (${vendors.data?.length ?? 0})`}
        actions={
          <Input
            placeholder="Search vendors..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64"
          />
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-2 pr-4">Factory Name</th>
                <th className="py-2 pr-4">Country</th>
                <th className="py-2 pr-4">Town</th>
                <th className="py-2 pr-4">Port of Loading</th>
                <th className="py-2 pr-4">Payment Terms</th>
                <th className="py-2 pr-4">Delivery Terms</th>
                {canManage && <th className="py-2 pr-4 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {(vendors.data ?? []).map((v) => (
                <tr key={v.id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-3 pr-4 font-medium text-slate-900 dark:text-slate-100">
                    {v.name}
                  </td>
                  <td className="py-3 pr-4 text-slate-600 dark:text-slate-400">
                    {v.country || "—"}
                  </td>
                  <td className="py-3 pr-4 text-slate-600 dark:text-slate-400">
                    {v.factory_town || "—"}
                  </td>
                  <td className="py-3 pr-4 text-slate-600 dark:text-slate-400">
                    {v.port_of_loading || "—"}
                  </td>
                  <td className="py-3 pr-4 text-slate-600 dark:text-slate-400">
                    {v.payment_terms || "—"}
                  </td>
                  <td className="py-3 pr-4 text-slate-600 dark:text-slate-400">
                    {v.terms_of_delivery || "—"}
                  </td>
                  {canManage && (
                    <td className="py-3 pr-0 text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" onClick={() => startEdit(v)}>
                          Edit
                        </Button>
                        <Button
                          variant="danger"
                          onClick={() => {
                            if (window.confirm(`Delete "${v.name}"?`))
                              deleteMutation.mutate(v.id);
                          }}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {vendors.data?.length === 0 && (
                <tr>
                  <td
                    colSpan={canManage ? 7 : 6}
                    className="py-6 text-center text-slate-400"
                  >
                    No vendors yet — upload a vendor order sheet and they will appear here.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
