"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, Input, Spinner, ErrorNote } from "@/components/ui";
import { canManageCustomers } from "@/lib/permissions";
import type { Customer } from "@/lib/types";

export default function CustomersPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const canManage = !!user && canManageCustomers(user.role);

  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formName, setFormName] = useState("");
  const [formAddress, setFormAddress] = useState("");
  const [formVat, setFormVat] = useState("");

  const customers = useQuery<Customer[]>({
    queryKey: ["customers", search],
    queryFn: () => api<Customer[]>(`/api/customers${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  });

  const createMutation = useMutation({
    mutationFn: (data: { name: string; address: string; vat_number: string }) =>
      api<Customer>("/api/customers", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: number; name: string; address: string; vat_number: string }) =>
      api<Customer>(`/api/customers/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/customers/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["customers"] }),
  });

  function resetForm() {
    setShowForm(false);
    setEditingId(null);
    setFormName("");
    setFormAddress("");
    setFormVat("");
  }

  function startEdit(c: Customer) {
    setEditingId(c.id);
    setFormName(c.name);
    setFormAddress(c.address ?? "");
    setFormVat(c.vat_number ?? "");
    setShowForm(true);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload = { name: formName, address: formAddress, vat_number: formVat };
    if (editingId) {
      updateMutation.mutate({ id: editingId, ...payload });
    } else {
      createMutation.mutate(payload);
    }
  }

  if (customers.isLoading) return <Spinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Customers</h1>
        {canManage && (
          <Button onClick={() => { resetForm(); setShowForm(!showForm); }}>
            {showForm ? "Cancel" : "Add customer"}
          </Button>
        )}
      </div>

      {customers.error && <ErrorNote message={(customers.error as Error).message} />}

      {(createMutation.error || updateMutation.error || deleteMutation.error) && (
        <ErrorNote message={
          (createMutation.error || updateMutation.error || deleteMutation.error as Error).message
        } />
      )}

      {showForm && (
        <Card title={editingId ? "Edit Customer" : "New Customer"}>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Company Name
              </label>
              <Input
                required
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Roman Originals PLC"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Address
              </label>
              <Input
                value={formAddress}
                onChange={(e) => setFormAddress(e.target.value)}
                placeholder="e.g. Unit 1, Vantage Point, 5 Wingfoot Close, Birmingham. B24 9JH"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">
                VAT Number
              </label>
              <Input
                value={formVat}
                onChange={(e) => setFormVat(e.target.value)}
                placeholder="e.g. GB 111 3607 23"
              />
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {editingId ? "Save changes" : "Create customer"}
              </Button>
              <Button variant="secondary" type="button" onClick={resetForm}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card
        title={`All Customers (${customers.data?.length ?? 0})`}
        actions={
          <Input
            placeholder="Search customers..."
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
                <th className="py-2 pr-4">Company Name</th>
                <th className="py-2 pr-4">Address</th>
                <th className="py-2 pr-4">VAT Number</th>
                {canManage && <th className="py-2 pr-4 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {(customers.data ?? []).map((c) => (
                <tr key={c.id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-3 pr-4 font-medium text-slate-900 dark:text-slate-100">
                    {c.name}
                  </td>
                  <td className="py-3 pr-4 text-slate-600 dark:text-slate-400">
                    {c.address || "—"}
                  </td>
                  <td className="py-3 pr-4 font-mono text-sm text-slate-600 dark:text-slate-400">
                    {c.vat_number || "—"}
                  </td>
                  {canManage && (
                    <td className="py-3 pr-0 text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" onClick={() => startEdit(c)}>
                          Edit
                        </Button>
                        <Button
                          variant="danger"
                          onClick={() => {
                            if (window.confirm(`Delete "${c.name}"?`)) {
                              deleteMutation.mutate(c.id);
                            }
                          }}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {customers.data?.length === 0 && (
                <tr>
                  <td colSpan={canManage ? 4 : 3} className="py-6 text-center text-slate-400">
                    No customers found.
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
