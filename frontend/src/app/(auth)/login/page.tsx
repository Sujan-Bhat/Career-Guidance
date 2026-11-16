"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { endpoints, isLoggedIn, storeTokens } from "@/lib/api/client";
import AuthShell from "@/components/auth/AuthShell";
import TextField from "@/components/auth/TextField";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  useEffect(() => {
    if (isLoggedIn()) router.replace("/dashboard");
  }, [router]);

  const executeLogin = async (loginEmail: string, loginPass: string) => {
    setBusy(true);
    setFormError(null);
    try {
      const { data } = await endpoints.auth.login(loginEmail.trim(), loginPass);
      storeTokens(data.access, data.refresh);
      router.push("/dashboard");
    } catch (err) {
      const apiErr = err as {
        response?: { status?: number; data?: { detail?: string } };
      };
      const status = apiErr?.response?.status;
      if (status === 401) {
        setFormError("Incorrect email or password.");
      } else if (status === 429) {
        setFormError(
          apiErr?.response?.data?.detail ??
            "Too many failed attempts. Try again in a few minutes."
        );
      } else {
        setFormError(
          apiErr?.response?.data?.detail ?? "Something went wrong. Please try again."
        );
      }
    } finally {
      setBusy(false);
      setDemoLoading(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors: typeof fieldErrors = {};
    if (!EMAIL_RE.test(email)) errors.email = "Enter a valid email address.";
    if (!password) errors.password = "Enter your password.";
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    await executeLogin(email, password);
  };

  const handleInstantDemoLogin = async () => {
    setEmail("demo@careermind.local");
    setPassword("Password123!");
    setFieldErrors({});
    setDemoLoading(true);
    await executeLogin("demo@careermind.local", "Password123!");
  };

  return (
    <AuthShell
      title="Welcome Back"
      subtitle="Sign in to resume tracking your Focus Efficiency Score."
      activeTab="login"
    >
      <div className="space-y-4">
        {/* ⚡ Instant 1-Click Demo Login Banner */}
        <button
          type="button"
          onClick={handleInstantDemoLogin}
          disabled={busy || demoLoading}
          className="group relative flex w-full items-center justify-between overflow-hidden rounded-xl border border-violet-500/40 bg-gradient-to-r from-violet-900/30 via-indigo-900/30 to-cyan-900/20 px-4 py-3 text-left transition-all hover:border-violet-400 hover:shadow-lg hover:shadow-violet-500/20 active:scale-[0.99] disabled:opacity-50"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-amber-400 to-orange-500 text-slate-950 font-bold shadow-md shadow-amber-500/20">
              ⚡
            </div>
            <div>
              <p className="text-xs font-bold text-white group-hover:text-violet-200 transition-colors">
                Quick Demo Access (1-Click)
              </p>
              <p className="text-[11px] text-slate-400">
                demo@careermind.local
              </p>
            </div>
          </div>
          <span className="flex items-center gap-1 text-xs font-semibold text-violet-300 group-hover:translate-x-0.5 transition-transform">
            {demoLoading ? (
              <span className="flex items-center gap-1.5">
                <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Entering…</span>
              </span>
            ) : (
              <span>Launch →</span>
            )}
          </span>
        </button>

        <div className="relative flex items-center justify-center">
          <div className="w-full border-t border-slate-800" />
          <span className="absolute bg-[#0E1526] px-3 text-[11px] uppercase tracking-wider text-slate-500">
            Or sign in with email
          </span>
        </div>

        <form className="flex flex-col gap-4" onSubmit={submit} noValidate>
          <TextField
            label="Email"
            type="email"
            icon="email"
            placeholder="you@university.edu"
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={fieldErrors.email}
          />

          <TextField
            label="Password"
            password
            icon="lock"
            placeholder="Your password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={fieldErrors.password}
          />

          {formError && (
            <div
              role="alert"
              className="flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-300"
            >
              <svg className="h-4 w-4 shrink-0 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{formError}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={busy || demoLoading}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-600 to-cyan-500 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition-all hover:from-violet-500 hover:to-cyan-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? (
              <>
                <svg className="h-4 w-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Authenticating…</span>
              </>
            ) : (
              <span>Sign In to Dashboard</span>
            )}
          </button>
        </form>

        <p className="text-center text-xs text-slate-400">
          Need an account?{" "}
          <Link href="/register" className="font-semibold text-violet-400 hover:text-violet-300 hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}
