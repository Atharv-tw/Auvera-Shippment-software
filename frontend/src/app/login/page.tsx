"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { useAuth } from "@/lib/auth";
import { Button, Input, ErrorNote } from "@/components/ui";
import { SELF_REGISTER_ROLES } from "@/lib/permissions";
import { ArrowLeft } from "lucide-react";

interface FormValues {
  email: string;
  password: string;
  name: string;
  role: string;
}

export default function LoginPage() {
  const { login, register: registerAccount } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormValues>({ defaultValues: { role: "merchant" } });

  const onSubmit = async (values: FormValues) => {
    setError(null);
    try {
      if (mode === "login") await login(values.email, values.password);
      else
        await registerAccount(
          values.email,
          values.password,
          values.name,
          values.role,
        );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* Left branding panel */}
      <div className="hidden flex-col items-center justify-center bg-slate-900 p-10 lg:flex lg:w-1/2">
        <div className="flex flex-col items-center gap-4 text-center">
          <Image
            src="/logo.png"
            alt="Auvera Studio Limited"
            width={80}
            height={80}
            className="h-20 w-20 rounded-2xl object-contain"
          />
          <div>
            <div className="text-lg font-bold text-white">Auvera Studio Limited</div>
            <div className="mt-1 text-[11px] font-medium uppercase tracking-widest text-slate-400">
              Apparel Sourcing
            </div>
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex w-full items-center justify-center p-6 lg:w-1/2">
        <div className="w-full max-w-sm">
          <Link
            href="/"
            className="mb-8 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <ArrowLeft size={14} />
            Back to home
          </Link>

          <div className="flex items-center gap-3 lg:hidden">
            <Image
              src="/logo.png"
              alt="Auvera Studio Limited"
              width={32}
              height={32}
              className="h-8 w-8 rounded-md object-contain"
            />
            <div>
              <div className="text-sm font-bold text-slate-900 dark:text-slate-50">
                Auvera Studio Limited
              </div>
              <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400 dark:text-slate-500">
                Apparel Sourcing
              </div>
            </div>
          </div>

          <h1 className="mt-6 text-xl font-bold text-slate-900 dark:text-slate-50">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {mode === "login"
              ? "Sign in to access the shipment tracker"
              : "Register a new account with your role"}
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-3">
            {mode === "register" && (
              <>
                <Input
                  placeholder="Your name"
                  {...register("name", { required: true })}
                />
                <select
                  {...register("role", { required: true })}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:focus:ring-blue-900/40"
                >
                  {SELF_REGISTER_ROLES.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </>
            )}
            <Input
              type="email"
              placeholder="Email address"
              autoComplete="email"
              {...register("email", { required: true })}
            />
            <Input
              type="password"
              placeholder="Password (min 6 characters)"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              {...register("password", { required: true, minLength: 6 })}
            />
            {error && <ErrorNote message={error} />}
            <Button
              type="submit"
              disabled={isSubmitting}
              className="w-full justify-center"
            >
              {isSubmitting
                ? "Please wait\u2026"
                : mode === "login"
                  ? "Sign in"
                  : "Create account"}
            </Button>
          </form>

          <button
            type="button"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            className="mt-4 w-full text-center text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            {mode === "login"
              ? "Need an account? Register"
              : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
