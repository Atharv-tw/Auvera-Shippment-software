"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge, Button, Select, Spinner, ErrorNote } from "@/components/ui";
import { ASSIGNABLE_ROLES, ROLE_LABELS, canManageUsers } from "@/lib/permissions";
import type { Role, UserAdmin } from "@/lib/types";

export default function UsersPage() {
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  // Admin-only. Non-admins are already kept out by the API (403), but redirect
  // rather than show them an error page.
  useEffect(() => {
    if (user && !canManageUsers(user.role)) router.replace("/dashboard");
  }, [user, router]);

  const users = useQuery<UserAdmin[]>({
    queryKey: ["admin-users"],
    queryFn: () => api<UserAdmin[]>("/api/admin/users"),
    enabled: !!user && canManageUsers(user.role),
  });

  const update = useMutation({
    mutationFn: ({ id, ...body }: { id: number; role?: Role; is_active?: boolean }) =>
      api<UserAdmin>(`/api/admin/users/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  if (!user || !canManageUsers(user.role)) return <Spinner />;

  const rows = users.data ?? [];
  const pendingCount = rows.filter((u) => u.role === "pending").length;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Users</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Approve new accounts and assign each person a role.
          {pendingCount > 0 && (
            <span className="ml-1 font-medium text-amber-600 dark:text-amber-400">
              {pendingCount} awaiting approval.
            </span>
          )}
        </p>
      </div>

      {update.error && (
        <ErrorNote
          message={
            update.error instanceof ApiError
              ? update.error.message
              : "Could not update the user"
          }
        />
      )}

      {users.isLoading ? (
        <Spinner />
      ) : users.error ? (
        <ErrorNote message="Could not load users" />
      ) : (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:text-slate-400">
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Role</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => (
                <UserRow
                  key={u.id}
                  u={u}
                  isSelf={u.id === user.id}
                  busy={update.isPending && update.variables?.id === u.id}
                  onRole={(role) => update.mutate({ id: u.id, role })}
                  onToggleActive={() => update.mutate({ id: u.id, is_active: !u.is_active })}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function UserRow({
  u,
  isSelf,
  busy,
  onRole,
  onToggleActive,
}: {
  u: UserAdmin;
  isSelf: boolean;
  busy: boolean;
  onRole: (role: Role) => void;
  onToggleActive: () => void;
}) {
  const pending = u.role === "pending";
  return (
    <tr
      className={
        pending
          ? "border-b border-slate-100 bg-amber-50/60 dark:border-slate-800 dark:bg-amber-500/5"
          : "border-b border-slate-100 dark:border-slate-800"
      }
    >
      <td className="px-4 py-3">
        <div className="font-medium text-slate-800 dark:text-slate-100">
          {u.name} {isSelf && <span className="text-xs text-slate-400">(you)</span>}
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400">{u.email}</div>
        <div className="text-[11px] text-slate-400">
          Joined {new Date(u.created_at).toLocaleDateString()}
        </div>
      </td>
      <td className="px-4 py-3">
        {/* The role select is the assignment control. Self is locked so an admin
            cannot demote themselves - the API refuses it too. */}
        <Select
          value={pending ? "" : u.role}
          disabled={isSelf || busy}
          onChange={(e) => e.target.value && onRole(e.target.value as Role)}
          className="w-44"
        >
          {pending && <option value="">Assign a role…</option>}
          {ASSIGNABLE_ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </Select>
      </td>
      <td className="px-4 py-3">
        {pending ? (
          <Badge color="yellow">Awaiting approval</Badge>
        ) : u.is_active ? (
          <Badge color="green">Active</Badge>
        ) : (
          <Badge color="gray">Disabled</Badge>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        {!isSelf && !pending && (
          <Button
            variant={u.is_active ? "secondary" : "primary"}
            disabled={busy}
            onClick={onToggleActive}
          >
            {u.is_active ? "Disable" : "Enable"}
          </Button>
        )}
        {isSelf && <span className="text-xs text-slate-400">{ROLE_LABELS[u.role]}</span>}
      </td>
    </tr>
  );
}
