"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { endpoints, storeTokens } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [programme, setProgramme] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { data } =
        mode === "login"
          ? await endpoints.auth.login(email, password)
          : await endpoints.auth.register({ email, full_name: fullName, password, programme });
      storeTokens(data.access, data.refresh);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center">
      <Card className="w-full max-w-sm" title={mode === "login" ? "Sign in" : "Create account"}>
        <form className="flex flex-col gap-3" onSubmit={submit}>
          {mode === "register" && (
            <>
              <input
                className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
                placeholder="Full name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
              <input
                className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
                placeholder="Programme (e.g., BE Computer Science)"
                value={programme}
                onChange={(e) => setProgramme(e.target.value)}
              />
            </>
          )}
          <input
            className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
            type="password"
            placeholder="Password (min 8 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={busy}>
            {busy ? "Please wait..." : mode === "login" ? "Login" : "Register"}
          </Button>
        </form>
        <button
          className="mt-4 w-full text-center text-sm text-primary hover:underline"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "No account? Register" : "Have an account? Login"}
        </button>
      </Card>
    </main>
  );
}
