
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
    leetcode_username?: string;
  leetcode_stats?: {
    total: number;
    easy: number;
    medium: number;
    hard: number;
    synced_at?: string;
  };
};

type FesBadge = {
  fes: number | null;
  tcr: number | null;
  sci: number | null;
} | null;

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [fes, setFes] = useState<FesBadge>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);

  const [fullName, setFullName] = useState("");
  const [programme, setProgramme] = useState("");
  const [year, setYear] = useState(3);
  const [fieldErrors, setFieldErrors] = useState<{ fullName?: string }>({});
  const [saveState, setSaveState] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [lcUsername, setLcUsername] = useState("");
  const [lcSyncing, setLcSyncing] = useState(false);
  const [lcError, setLcError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const { data } = await endpoints.auth.me();
      setProfile(data);
      setFullName(data.full_name ?? "");
      setProgramme(data.programme ?? "");
      setYear(data.year_of_study ?? 3);
      setLoadError(null);
      setNeedsLogin(false);
    } catch (err) {
      if ((err as { response?: { status?: number } })?.response?.status === 401) {
        setNeedsLogin(true);
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
      .catch(() => setFes(null));
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
    } catch (err) {
      setSaveState("error");
      setSaveError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Could not save changes."
      );
    }
  };

  if (needsLogin) {
    return (
      <div className="min-h-screen bg-[#0B1020] px-6 py-10 text-slate-100">
        <p className="text-sm text-slate-400">
          Your session has ended.{" "}
          <a
            href="/login"
            className="font-medium text-violet-400 hover:text-violet-300 hover:underline"
          >
            Log in
          </a>{" "}
          to view your profile.
        </p>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="min-h-screen bg-[#0B1020] px-6 py-10">
        <p className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          {loadError}
        </p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-[#0B1020] px-6 py-10">
        <p className="text-sm text-slate-400">Loading profile…</p>
      </div>
    );
  }

  const handleSyncLeetcode = async () => {
    if (!lcUsername.trim()) return;
    setLcSyncing(true);
    setLcError(null);
    try {
      const { data } = await endpoints.leetcode.sync(lcUsername.trim());
      setProfile((prev) => (prev ? { ...prev, ...data } : prev));
    } catch {
      setLcError("Could not find that LeetCode username.");
    } finally {
      setLcSyncing(false);
    }
  };
  const dirty =
    fullName !== (profile.full_name ?? "") ||
    programme !== (profile.programme ?? "") ||
    year !== (profile.year_of_study ?? 3);

  const cardStyle =
    "!border !border-slate-800 !bg-[#111827] !text-slate-100 !shadow-lg !shadow-black/10";

  const labelStyle =
    "mb-1 block text-sm font-medium text-slate-300";

  const inputStyle =
    "w-full rounded-lg border border-slate-700 bg-[#0B1020] px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-400";

  return (
    <div className="min-h-screen bg-[#0B1020] px-4 py-8 text-slate-100 sm:px-6">
      <div className="mx-auto max-w-5xl space-y-7">
        {/* Page heading */}
        <header className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">
              Account settings
            </p>
            <h1 className="text-3xl font-bold tracking-tight text-white">
              {profile.full_name || "Your profile"}
            </h1>
            <p className="mt-2 text-sm text-slate-400">
              {profile.email}
              {profile.programme ? ` · ${profile.programme}` : ""}
              {profile.year_of_study
                ? ` · Year ${profile.year_of_study}`
                : ""}
            </p>
          </div>

          {/* Focus Efficiency Score */}
          {fes &&
            (fes.fes != null || fes.tcr != null || fes.sci != null) && (
              <div className="min-w-56 rounded-xl border border-violet-500/30 bg-violet-500/10 px-5 py-4 sm:text-right">
                <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
                  Focus Efficiency Score
                </p>
                <p className="mt-1 text-3xl font-bold tabular-nums text-violet-300">
                  {fes.fes != null ? fes.fes.toFixed(3) : "—"}
                </p>
                <p className="mt-2 text-xs text-slate-400">
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

        {/* Personal details */}
        <Card title="Personal details" className={cardStyle}>
          <form className="flex flex-col gap-5" onSubmit={save}>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <TextField
                label="Full name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                error={fieldErrors.fullName}
              />

              <div>
                <label className={labelStyle}>Email</label>
                <input
                  disabled
                  value={profile.email}
                  className={inputStyle}
                />
                <p className="mt-1.5 text-xs text-slate-500">
                  Your email address cannot be edited here.
                </p>
              </div>

              <TextField
                label="Programme"
                placeholder="e.g., BE Computer Science"
                value={programme}
                onChange={(e) => setProgramme(e.target.value)}
              />

              <div>
                <label htmlFor="profile-year" className={labelStyle}>
                  Year of study
                </label>
                <select
                  id="profile-year"
                  value={year}
                  onChange={(e) => setYear(Number(e.target.value))}
                  className={inputStyle}
                >
                  {[1, 2, 3, 4].map((y) => (
                    <option
                      key={y}
                      value={y}
                      className="bg-[#111827] text-slate-100"
                    >
                      Year {y}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 pt-4">
              <Button
                type="submit"
                disabled={!dirty || saveState === "saving"}
                className="!rounded-lg !border !border-teal-500 !bg-teal-700 !px-5 !py-2.5 !font-semibold !text-white !transition-all hover:!border-teal-400 hover:!bg-teal-600 disabled:!cursor-not-allowed disabled:!opacity-50"
              >
                {saveState === "saving" ? "Saving…" : "Save changes"}
              </Button>

              {saveState === "saved" && (
                <span className="text-sm font-medium text-emerald-400">
                  Saved ✓
                </span>
              )}

              {saveState === "error" && (
                <span className="text-sm text-red-400">{saveError}</span>
              )}
            </div>
          </form>
        </Card>

        {/* Records and preferences */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <Card
            title={`Academic records (${profile.academic_records.length})`}
            className={cardStyle}
          >
            {profile.academic_records.length === 0 ? (
              <p className="text-sm text-slate-500">No records yet.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {profile.academic_records.map((record, i) => (
                  <li
                    key={i}
                    className="flex justify-between gap-3 border-b border-slate-800 pb-3 last:border-0 last:pb-0"
                  >
                    <span className="text-slate-300">
                      {record.subject ?? "Record"}
                    </span>
                    <span className="font-semibold tabular-nums text-slate-100">
                      {String(record.grade ?? record.score ?? "—")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card
            title={`Skill assessments (${profile.skill_assessments.length})`}
            className={cardStyle}
          >
            {profile.skill_assessments.length === 0 ? (
              <p className="text-sm text-slate-500">No assessments yet.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {profile.skill_assessments.map((record, i) => (
                  <li
                    key={i}
                    className="flex justify-between gap-3 border-b border-slate-800 pb-3 last:border-0 last:pb-0"
                  >
                    <span className="text-slate-300">
                      {record.skill ?? record.subject ?? "Skill"}
                    </span>
                    <span className="font-semibold tabular-nums text-slate-100">
                      {String(record.score ?? "—")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card
            title={`Career preferences (${profile.career_preferences.length})`}
            className={cardStyle}
          >
            {profile.career_preferences.length === 0 ? (
              <p className="text-sm text-slate-500">No preferences yet.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {profile.career_preferences.map((record, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-slate-800 bg-[#0B1020] px-3 py-2.5 text-slate-300"
                  >
                    {record.pathway ??
                      record.name ??
                      record.title ??
                      JSON.stringify(record)}
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="LeetCode Profile" className={`${cardStyle} min-w-0 overflow-hidden`}>
  <div className="flex w-full min-w-0 flex-col gap-4">
    <div className="flex w-full min-w-0 flex-wrap gap-2">
      <input
        type="text"
        value={lcUsername}
        onChange={(e) => setLcUsername(e.target.value)}
        placeholder="Enter LeetCode username"
        className="w-full min-w-0 flex-1 basis-40 rounded-lg border border-slate-800 bg-[#0B1020] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-violet-500 focus:outline-none"
      />
      <Button
        type="button"
        onClick={handleSyncLeetcode}
        disabled={lcSyncing}
        className="shrink-0 whitespace-nowrap max-sm:w-full"
      >
        {lcSyncing ? "Syncing..." : "Link & Sync"}
      </Button>
    </div>

    {lcError && <p className="text-xs text-rose-400">{lcError}</p>}

    {!profile?.leetcode_stats ? (
      <p className="text-sm text-slate-500">No LeetCode account linked yet.</p>
    ) : (
      <ul className="space-y-3 text-sm">
        {[
          { label: "Total Solved", value: profile.leetcode_stats.total },
          { label: "Easy", value: profile.leetcode_stats.easy },
          { label: "Medium", value: profile.leetcode_stats.medium },
          { label: "Hard", value: profile.leetcode_stats.hard },
        ].map((item) => (
          <li
            key={item.label}
            className="flex justify-between gap-3 border-b border-slate-800 pb-3 last:border-0 last:pb-0"
          >
            <span className="text-slate-300">{item.label}</span>
            <span className="font-semibold tabular-nums text-slate-100">
              {item.value}
            </span>
          </li>
        ))}
      </ul>
    )}
  </div>
</Card>
        </div>
      </div>
    </div>
  );
}
