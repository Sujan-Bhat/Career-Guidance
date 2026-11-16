"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { endpoints, isLoggedIn, storeTokens } from "@/lib/api/client";
import AuthShell from "@/components/auth/AuthShell";
import TextField from "@/components/auth/TextField";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const STRENGTH_LEVELS = [
  { label: "Too weak", bar: "bg-red-500", text: "text-red-400" },
  { label: "Weak", bar: "bg-orange-500", text: "text-orange-400" },
  { label: "Fair", bar: "bg-amber-500", text: "text-amber-400" },
  { label: "Good", bar: "bg-cyan-500", text: "text-cyan-400" },
  { label: "Strong", bar: "bg-emerald-500", text: "text-emerald-400" },
];

function passwordStrength(pw: string): number {
  if (!pw) return 0;
  let score = 0;
  if (pw.length >= 8) score += 1;
  if (pw.length >= 12) score += 1;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score += 1;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score += 1;
  return Math.min(score, 4);
}

type FieldErrors = Partial<
  Record<"fullName" | "email" | "programme" | "password" | "confirm" | "year", string>
>;

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [programme, setProgramme] = useState("");
  const [year, setYear] = useState(3);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (isLoggedIn()) router.replace("/dashboard");
  }, [router]);

  const strength = passwordStrength(password);
  const strengthUi = STRENGTH_LEVELS[strength];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors: FieldErrors = {};
    if (fullName.trim().length < 2) errors.fullName = "Enter your full name.";
    if (!EMAIL_RE.test(email)) errors.email = "Enter a valid email address.";
    if (password.length < 8) errors.password = "Use at least 8 characters.";
    if (confirm !== password) errors.confirm = "Passwords don't match.";
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setBusy(true);
    setFormError(null);
    try {
      const { data } = await endpoints.auth.register({
        email: email.trim(),
        full_name: fullName.trim(),
        password,
        programme: programme.trim(),
        year_of_study: year,
      });
      storeTokens(data.access, data.refresh);
      router.push("/dashboard");
    } catch (err) {
      const data = (
        err as {
          response?: {
            data?: { detail?: string; [field: string]: string[] | string | undefined };
          };
        }
      )?.response?.data;
      const errors: FieldErrors = {};
      if (data && typeof data === "object" && !data.detail) {
        if (data.email) errors.email = String(data.email[0]);
        if (data.full_name) errors.fullName = String(data.full_name[0]);
        if (data.password) errors.password = String(data.password[0]);
        if (data.year_of_study) errors.year = String(data.year_of_study[0]);
        setFieldErrors(errors);
      } else if (data?.detail === "Email already registered") {
        setFieldErrors({ email: "That email is already registered." });
      } else {
        setFormError(data?.detail ?? "Could not create your account. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell
      title="Create Student Profile"
      subtitle="Join CAREERMIND and calibrate your behavioral study metrics."
      activeTab="register"
    >
      <form className="flex flex-col gap-3.5" onSubmit={submit} noValidate>
        <TextField
          label="Full Name"
          icon="user"
          placeholder="Ada Lovelace"
          autoComplete="name"
          autoFocus
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          error={fieldErrors.fullName}
        />

        <TextField
          label="Email Address"
          type="email"
          icon="email"
          placeholder="ada@university.edu"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldErrors.email}
        />

        <div className="grid grid-cols-3 gap-2.5">
          <div className="col-span-2">
            <TextField
              label="Degree / Major"
              icon="school"
              placeholder="e.g. Computer Science"
              value={programme}
              onChange={(e) => setProgramme(e.target.value)}
              error={fieldErrors.programme}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Year
            </label>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="w-full rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-2.5 text-sm text-slate-100 shadow-inner shadow-black/20 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/25"
            >
              {[1, 2, 3, 4, 5, 6].map((y) => (
                <option key={y} value={y} className="bg-slate-900">
                  Year {y}
                </option>
              ))}
            </select>
          </div>
        </div>

        <TextField
          label="Password"
          password
          icon="lock"
          placeholder="At least 8 characters"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
        />

        {/* Live Password Strength Meter */}
        {password && (
          <div className="space-y-1.5 rounded-lg border border-slate-800 bg-slate-950/40 p-2.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-400">Strength:</span>
              <span className={`font-semibold ${strengthUi.text}`}>{strengthUi.label}</span>
            </div>
            <div className="flex h-1.5 w-full gap-1 overflow-hidden rounded-full bg-slate-800">
              {[0, 1, 2, 3].map((lvl) => (
                <div
                  key={lvl}
                  className={`h-full flex-1 transition-all duration-300 ${
                    strength > lvl ? strengthUi.bar : "bg-slate-800"
                  }`}
                />
              ))}
            </div>
          </div>
        )}

        <TextField
          label="Confirm Password"
          password
          icon="lock"
          placeholder="Re-enter password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={fieldErrors.confirm}
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
          disabled={busy}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-600 to-cyan-500 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition-all hover:from-violet-500 hover:to-cyan-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? (
            <>
              <svg className="h-4 w-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>Creating Profile…</span>
            </>
          ) : (
            <span>Create Account & Start</span>
          )}
        </button>

        <p className="text-center text-xs text-slate-400">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-violet-400 hover:text-violet-300 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
