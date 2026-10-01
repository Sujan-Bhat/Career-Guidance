"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { endpoints, isLoggedIn, storeTokens } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import AuthShell from "@/components/auth/AuthShell";
import TextField from "@/components/auth/TextField";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const STRENGTH_LEVELS = [
  { label: "Too weak", bar: "bg-red-500", text: "text-red-600" },
  { label: "Weak", bar: "bg-orange-500", text: "text-orange-600" },
  { label: "Fair", bar: "bg-amber-500", text: "text-amber-600" },
  { label: "Good", bar: "bg-lime-500", text: "text-lime-700" },
  { label: "Strong", bar: "bg-green-600", text: "text-green-700" },
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
    } catch (err: any) {
      const data = err?.response?.data;
      const errors: FieldErrors = {};
      if (data && typeof data === "object" && !data.detail) {
        // DRF field-keyed validation errors: {email: ["Enter a valid email address."]}
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
      title="Create your account"
      subtitle="Start tracking your focus and get matched to pathways."
    >
      <form className="flex flex-col gap-4" onSubmit={submit} noValidate>
        <TextField
          label="Full name"
          placeholder="Ada Lovelace"
          autoComplete="name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          error={fieldErrors.fullName}
        />
        <TextField
          label="Email"
          type="email"
          placeholder="you@university.edu"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldErrors.email}
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_7rem]">
          <TextField
            label="Programme"
            placeholder="e.g., BE Computer Science"
            hint="Optional"
            value={programme}
            onChange={(e) => setProgramme(e.target.value)}
            error={fieldErrors.programme}
          />
          <div>
            <label htmlFor="year" className="mb-1 block text-sm font-medium text-slate-700">
              Year
            </label>
            <select
              id="year"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              {[1, 2, 3, 4, 5, 6].map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            {fieldErrors.year && <p className="mt-1 text-xs text-red-600">{fieldErrors.year}</p>}
          </div>
        </div>
        <div>
          <TextField
            label="Password"
            password
            placeholder="At least 8 characters"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={fieldErrors.password}
          />
          {password.length > 0 && (
            <div className="mt-2 flex items-center gap-2">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                <div
                  className={`h-full transition-all ${strengthUi.bar}`}
                  style={{ width: `${(strength / 4) * 100}%` }}
                />
              </div>
              <span className={`w-16 text-right text-xs font-medium ${strengthUi.text}`}>
                {strengthUi.label}
              </span>
            </div>
          )}
        </div>
        <TextField
          label="Confirm password"
          password
          placeholder="Repeat your password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={fieldErrors.confirm}
        />
        {formError && (
          <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">
            {formError}
          </p>
        )}
        <Button type="submit" disabled={busy} className="mt-2 w-full">
          {busy ? "Creating account…" : "Create account"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
