"use client";

import { useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button, Spinner } from "@/components/ui";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Clock } from "lucide-react";

/** Where a freshly-registered account waits until an admin assigns it a role.
 * It sits outside the `(app)` route group, so it has no sidebar and no access
 * to any feature - only the signed-in user's own details and a sign-out. */
export default function WaitlistPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (user.role !== "pending") router.replace("/dashboard");
  }, [loading, user, router]);

  if (loading || !user || user.role !== "pending") return <Spinner />;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-slate-50 px-6 py-12 text-center dark:bg-slate-950">
      <Image
        src="/logo.png"
        alt="Auvera Studio Limited"
        width={64}
        height={64}
        className="h-16 w-16 rounded-2xl object-contain"
      />
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-amber-100 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400">
        <Clock size={26} />
      </div>
      <div className="space-y-2">
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
          Your account is awaiting approval
        </h1>
        <p className="max-w-md text-sm text-slate-500 dark:text-slate-400">
          Thanks for signing up, {user.name}. An administrator needs to approve
          your account and assign your access before you can use the tracker.
          You&apos;ll be able to sign in normally once that&apos;s done.
        </p>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Signed in as {user.email}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <Button variant="secondary" onClick={logout}>
          Sign out
        </Button>
      </div>
    </div>
  );
}
