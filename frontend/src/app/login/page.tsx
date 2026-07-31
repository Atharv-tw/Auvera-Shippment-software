"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { useAuth } from "@/lib/auth";
import { Button, Input, ErrorNote } from "@/components/ui";

interface FormValues {
  email: string;
  password: string;
  name: string;
}

export default function LoginPage() {
  const { login, register: registerAccount } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormValues>();

  const onSubmit = async (values: FormValues) => {
    setError(null);
    try {
      if (mode === "login") await login(values.email, values.password);
      else await registerAccount(values.email, values.password, values.name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
          Order &amp; Shipment Tracker
        </h1>
        <p className="mb-6 mt-1 text-sm text-slate-500 dark:text-slate-400">
          {mode === "login" ? "Sign in to your account" : "Create a vendor account"}
        </p>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
          {mode === "register" && (
            <Input placeholder="Your name" {...register("name", { required: true })} />
          )}
          <Input
            type="email"
            placeholder="Email"
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
          <Button type="submit" disabled={isSubmitting} className="w-full justify-center">
            {isSubmitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="mt-4 w-full text-center text-sm text-blue-600 hover:underline"
        >
          {mode === "login" ? "Need an account? Register" : "Already have an account? Sign in"}
        </button>
      </div>
    </div>
  );
}
