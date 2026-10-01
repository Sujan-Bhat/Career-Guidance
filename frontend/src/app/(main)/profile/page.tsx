"use client";

import { useCallback, useEffect, useState } from "react";
import { endpoints } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import TextField from "@/components/auth/TextField";

type EmbeddedRecord = {
  subject?: string;
  skill?: string;
  score?: number;
  grade?: number;
  pathway?: string;
  name?: string;
  title?: string;
  [key: string]: unknown;
};

type Profile = {
  email: string;
  full_name: string;
  programme: string;
  year_of_study: number;
  academic_records: EmbeddedRecord[];
  skill_assessments: EmbeddedRecord[];
  career_preferences: EmbeddedRecord[];
};

type FesBadge = { fes: number | null; tcr: number | null; sci: number | null } | null;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [fes, setFes] = useState<FesBadge>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);

  const [fullName, setFullName] = useState("");
  const [programme, setProgramme] = useState("");
  const [year, setYear] = useState(3);
  const [fieldErrors, setFieldErrors] = useState<{ fullName?: string }>({});
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const { data } = await endpoints.auth.me();
      setProfile(data);
      setFullName(data.full_name ?? "");
      setProgramme(data.programme ?? "");
      setYear(data.year_of_study ?? 3);
      setLoadError(null);
      setNeedsLogin(false);
    } catch (err: any) {
      if (err?.response?.status === 401) {
        setNeedsLogin(true); // silent refresh already ran and failed
      } else {
        setLoadError("Could not load your profile. Try refreshing the page.");
      }
    }
  }, []);

  useEffect(() => {
    load();
    endpoints.fes
      .current()
      .then(({ data }) =>
        setFes({ fes: data.fes, tcr: data.tcr, sci: data.sci })
      )
      .catch(() => setFes(null)); // no FES history yet — badge simply hides
  }, [load]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (fullName.trim().length < 2) {
      setFieldErrors({ fullName: "Enter your full name." });
      return;
    }
    setFieldErrors({});
    setSaveState("saving");
    setSaveError(null);
    try {
      const { data } = await endpoints.auth.updateMe({
        full_name: fullName.trim(),
        programme: programme.trim(),
        year_of_study: year,
      });
      setProfile((prev) => (prev ? { ...prev, ...data } : data));
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 2000);
    } catch (err: any) {
      setSaveState("error");
      setSaveError(err?.response?.data?.detail ?? "Could not save changes.");
    }
  };

  if (needsLogin) {
    return (
      <p className="text-sm text-slate-600">
        Your session has ended.{" "}
        <a href="/login" className="font-medium text-primary hover:underline">
          Log in
        </a>{" "}
        to view your profile.
      </p>
    );
  }
  if (loadError) {
    return <p className="text-sm text-red-600">{loadError}</p>;
  }
  if (!profile) {
    return <p className="text-sm text-slate-500">Loading profile…</p>;
  }

  const dirty =
    fullName !== (profile.full_name ?? "") ||
    programme !== (profile.programme ?? "") ||
    year !== (profile.year_of_study ?? 3);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{profile.full_name || "Your profile"}</h1>
          <p className="text-sm text-slate-500">
            {profile.email}
            {profile.programme ? ` · ${profile.programme}` : ""}
            {profile.year_of_study ? ` · Year ${profile.year_of_study}` : ""}
          </p>
        </div>
        {fes && (fes.fes != null || fes.tcr != null || fes.sci != null) && (
          <div className="rounded-lg border border-primary-light bg-primary-light/50 px-4 py-3 text-right">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Focus Efficiency Score
            </p>
            <p className="text-2xl font-bold text-primary">
              {fes.fes != null ? fes.fes.toFixed(3) : "—"}
            </p>
            <p className="text-xs text-slate-500">
              {[
                fes.tcr != null ? `TCR ${fes.tcr.toFixed(2)}` : null,
                fes.sci != null ? `SCI ${fes.sci.toFixed(2)}` : null,
              ]
                .filter(Boolean)
                .join(" · ") || "Sub-metrics pending"}
            </p>
          </div>
        )}
      </header>

      <Card title="Personal details">
        <form className="flex flex-col gap-4" onSubmit={save}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <TextField
              label="Full name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              error={fieldErrors.fullName}
            />
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
              <input
                disabled
                value={profile.email}
                className="w-full cursor-not-allowed rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500"
              />
            </div>
            <TextField
              label="Programme"
              placeholder="e.g., BE Computer Science"
              value={programme}
              onChange={(e) => setProgramme(e.target.value)}
            />
            <div>
              <label htmlFor="profile-year" className="mb-1 block text-sm font-medium text-slate-700">
                Year of study
              </label>
              <select
                id="profile-year"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                {[1, 2, 3, 4, 5, 6].map((y) => (
                  <option key={y} value={y}>
                    Year {y}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={!dirty || saveState === "saving"}>
              {saveState === "saving" ? "Saving…" : "Save changes"}
            </Button>
            {saveState === "saved" && <span className="text-sm text-green-700">Saved ✓</span>}
            {saveState === "error" && (
              <span className="text-sm text-red-600">{saveError}</span>
            )}
          </div>
        </form>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card title={`Academic records (${profile.academic_records.length})`}>
          {profile.academic_records.length === 0 ? (
            <p className="text-sm text-slate-400">No records yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {profile.academic_records.map((record, i) => (
                <li key={i} className="flex justify-between gap-2">
                  <span className="text-slate-700">{record.subject ?? "Record"}</span>
                  <span className="font-medium text-slate-900">
                    {String(record.grade ?? record.score ?? "—")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={`Skill assessments (${profile.skill_assessments.length})`}>
          {profile.skill_assessments.length === 0 ? (
            <p className="text-sm text-slate-400">No assessments yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {profile.skill_assessments.map((record, i) => (
                <li key={i} className="flex justify-between gap-2">
                  <span className="text-slate-700">{record.skill ?? record.subject ?? "Skill"}</span>
                  <span className="font-medium text-slate-900">
                    {String(record.score ?? "—")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={`Career preferences (${profile.career_preferences.length})`}>
          {profile.career_preferences.length === 0 ? (
            <p className="text-sm text-slate-400">No preferences yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {profile.career_preferences.map((record, i) => (
                <li key={i} className="text-slate-700">
                  {record.pathway ?? record.name ?? record.title ?? JSON.stringify(record)}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
