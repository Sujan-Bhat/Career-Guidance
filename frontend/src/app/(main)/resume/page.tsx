"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { usePersistedState } from "@/lib/persistance/usePersistedState";
import {
  isJobRunning,
  runBackgroundJob,
  subscribeJob,
} from "@/lib/persistance/resumeJobs";
import { Button } from "@/components/ui/Button";
import { ScoreRing } from "@/components/ui/ScoreRing";

const CAREER_PATHWAYS = [
  { id: "c01", name: "Software Engineer" },
  { id: "c02", name: "Full-Stack Developer" },
  { id: "c03", name: "Data Scientist" },
  { id: "c04", name: "Data Engineer" },
  { id: "c05", name: "Machine Learning Engineer" },
  { id: "c06", name: "DevOps Engineer" },
  { id: "c07", name: "Cloud Architect" },
  { id: "c08", name: "Cybersecurity Analyst" },
];

const POPULAR_SKILLS = [
  "programming_python",
  "dsa",
  "javascript_ts",
  "web_frontend",
  "web_backend",
  "databases_sql",
  "cloud_platforms",
  "ml_fundamentals",
  "operating_systems",
];

interface AnalysisResult {
  ats_score: number;
  verdict: {
    status: "ready" | "needs_upskilling" | "needs_resume_polish";
    summary: string;
  };
  skill_analysis: {
    matched_skills: { name: string; level: number; evidence?: string }[];
    missing_skills: { name: string; target_level: number; reason?: string }[];
  };
  company_fit: {
    target_companies: string;
    evaluation: string;
    hiring_bar_advice: string;
  };
  resume_building_tips: string[];
  learning_roadmap: string[];
}
type SavedPdf = { name: string; dataUrl: string } | null;

export default function ResumeAnalysisPage() {
const [file, setFile] = useState<File | null>(null); // Keep File in useState (browsers can't serialize PDF File objects)
const [savedPdf, setSavedPdf] = usePersistedState<SavedPdf>("cm_resume_pdf", null);
const [pathwayId, setPathwayId] = usePersistedState("cm_resume_pathway", "c01");
const [targetCompanies, setTargetCompanies] = usePersistedState(
  "cm_resume_companies",
  "Google, Microsoft, Amazon"
);
const [selectedSkills, setSelectedSkills] = usePersistedState<string[]>(
  "cm_resume_skills",
  ["programming_python", "databases_sql"]
);

const [loading, setLoading] = useState(() => isJobRunning());
useEffect(() => {
  setLoading(isJobRunning());
  return subscribeJob(() => setLoading(isJobRunning()));
}, []);
const [error, setError] = useState<string | null>(null);
const [result, setResult] = usePersistedState<AnalysisResult | null>(
  "cm_resume_result",
  null
);
  const toggleSkill = (skill: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill]
    );
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    let pdfToSend = file;
    if (!pdfToSend && savedPdf) {
      const blob = await (await fetch(savedPdf.dataUrl)).blob();
      pdfToSend = new File([blob], savedPdf.name, { type: "application/pdf" });
    }
    if (!pdfToSend) {
      setError("Please select a PDF resume file first.");
      return;
    }

    setError(null);

    const formData = new FormData();
    formData.append("resume", pdfToSend);
    formData.append("pathway_id", pathwayId);
    formData.append("target_companies", targetCompanies);
    formData.append("specified_skills", selectedSkills.join(","));

    try {
      const data = await runBackgroundJob<AnalysisResult>(
        "/api/v1/careers/resume-analysis",
        formData,
        "cm_resume_result"
      );
      setResult(data);
    } catch (err: unknown) {
      const apiError = err as { response?: { data?: { detail?: string } } };
      setError(
        apiError?.response?.data?.detail ??
          "Failed to analyze resume. Please verify your token and file."
      );
    }
  };

  const cardStyle =
    "!border !border-slate-800 !bg-[#111827] !text-slate-100 !shadow-lg !shadow-black/10";

  return (
    <div className="min-h-screen bg-[#0B1020] px-4 py-8 text-slate-100 sm:px-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        {/* Header */}
        <header>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">
            AI Career Advisor
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Resume & Skill Gap Analyzer
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Upload your resume, target high-tier companies, and discover exactly
            what hiring managers and ATS algorithms look for.
          </p>
        </header>

        {/* Form Upload Section */}
        <Card title="Upload & Target Roles" className={cardStyle}>
          <form onSubmit={handleAnalyze} className="space-y-6">
            {/* File Upload Box */}
            <div>
              <label className="block text-sm font-medium text-slate-300">
                PDF Resume
              </label>
              <div className="mt-2 flex justify-center rounded-xl border border-dashed border-slate-700 bg-[#0B1020] px-6 py-6 transition-colors hover:border-violet-500">
                <div className="text-center">
                  <input
                    id="resume-upload"
                    type="file"
                    accept=".pdf"
                    className="sr-only"
                    onChange={(e) => {
                      const picked = e.target.files?.[0];
                      if (!picked) return;
                      setFile(picked);
                      const reader = new FileReader();
                      reader.onload = () => {
                        setSavedPdf({ name: picked.name, dataUrl: String(reader.result) });
                      };
                      reader.readAsDataURL(picked);
                    }}
                  />
                  <label
                    htmlFor="resume-upload"
                    className="cursor-pointer font-medium text-violet-400 hover:text-violet-300"
                  >
                    {(file?.name ?? savedPdf?.name) || "Click to select a .pdf file"}
                  </label>
                  <p className="mt-1 text-xs text-slate-500">
                    PDF files only (maximum 5MB)
                  </p>
                </div>
              </div>
            </div>

            {/* Target Pathway & Target Companies */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-slate-300">
                  Target Career Pathway
                </label>
                <select
                  value={pathwayId}
                  onChange={(e) => setPathwayId(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-[#0B1020] px-3 py-2 text-sm text-slate-200 focus:border-violet-500 focus:outline-none"
                >
                  {CAREER_PATHWAYS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300">
                  Target Companies
                </label>
                <input
                  type="text"
                  value={targetCompanies}
                  onChange={(e) => setTargetCompanies(e.target.value)}
                  placeholder="e.g. Google, Microsoft, Stripe"
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-[#0B1020] px-3 py-2 text-sm text-slate-200 focus:border-violet-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Priority Skills Chips */}
            <div>
              <label className="block text-sm font-medium text-slate-300">
                Key Skills to Highlight (Click to toggle)
              </label>
              <div className="mt-2 flex flex-wrap gap-2">
                {POPULAR_SKILLS.map((skill) => {
                  const active = selectedSkills.includes(skill);
                  return (
                    <button
                      key={skill}
                      type="button"
                      onClick={() => toggleSkill(skill)}
                      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                        active
                          ? "bg-violet-600 text-white"
                          : "border border-slate-700 bg-slate-800 text-slate-400 hover:text-white"
                      }`}
                    >
                      {skill.replace(/_/g, " ")} {active ? "✓" : "+"}
                    </button>
                  );
                })}
              </div>
            </div>

            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
                {error}
              </div>
            )}

            {loading && (
              <div className="relative overflow-hidden rounded-2xl border border-violet-500/40 bg-gradient-to-r from-violet-950/40 via-indigo-950/40 to-slate-900/80 p-5 shadow-xl backdrop-blur-md animate-in fade-in duration-300">
                <div className="absolute top-0 inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-cyan-400 to-transparent animate-pulse" />
                <div className="flex items-center gap-4">
                  <div className="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-violet-600/20 border border-violet-500/40">
                    <div className="absolute inset-0 rounded-xl border-2 border-violet-400/50 border-t-transparent animate-spin" />
                    <svg className="h-5 w-5 text-cyan-300 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-cyan-400 animate-ping" />
                      <p className="text-xs font-bold uppercase tracking-wider text-violet-300">
                        AI Resume & ATS Parser Running
                      </p>
                    </div>
                    <p className="text-xs text-slate-300 font-medium">
                      Scanning technical keywords, calculating ATS score & detecting skill gaps...
                    </p>
                  </div>
                </div>
                <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                  <div className="h-full w-2/5 rounded-full bg-gradient-to-r from-violet-500 via-indigo-400 to-cyan-400 animate-[bounce_2s_infinite]" />
                </div>
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full !rounded-xl !bg-gradient-to-r !from-violet-600 !via-indigo-600 !to-cyan-500 !py-3 font-semibold !text-white shadow-lg shadow-violet-500/20 hover:!from-violet-500 hover:!to-cyan-400 active:scale-[0.98] transition-all"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-4 w-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Processing Analysis with Advanced Career Mind AI…</span>
                </span>
              ) : (
                "Analyze Resume & Companies"
              )}
            </Button>
          </form>
        </Card>

        {/* Results Section */}
        {result && (
          <div className="space-y-6">
            {/* ATS Score & Verdict */}
            <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
              <Card title="ATS Match Score" className={`${cardStyle} flex flex-col items-center justify-center`}>
                <ScoreRing value={result.ats_score / 100} label="ATS Score" />
                <span
                  className={`mt-2 rounded-full px-3 py-0.5 text-xs font-semibold ${
                    result.ats_score >= 80
                      ? "bg-emerald-500/20 text-emerald-400"
                      : result.ats_score >= 60
                      ? "bg-amber-500/20 text-amber-400"
                      : "bg-red-500/20 text-red-400"
                  }`}
                >
                  {result.ats_score >= 80 ? "Interview Ready" : "Optimization Needed"}
                </span>
              </Card>

              <Card title="AI Career Verdict" className={`${cardStyle} md:col-span-2`}>
                <div className="flex flex-col justify-between h-full">
                  <div>
                    <h3 className="text-lg font-bold text-violet-300 capitalize">
                      {result.verdict.status.replace(/_/g, " ")}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-slate-300">
                      {result.verdict.summary}
                    </p>
                  </div>
                  <div className="mt-4 border-t border-slate-800 pt-3 text-xs text-slate-500">
                    Evaluated against standards for {pathwayId.toUpperCase()} & target firms.
                  </div>
                </div>
              </Card>
            </div>

            {/* Target Company Fit */}
            <Card title={`Company Fit: ${result.company_fit.target_companies}`} className={cardStyle}>
              <p className="text-sm leading-relaxed text-slate-200">
                {result.company_fit.evaluation}
              </p>
              <div className="mt-4 rounded-lg border border-violet-500/30 bg-violet-500/10 p-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-violet-300">
                  Target Company Hiring Bar:
                </span>
                <p className="mt-1 text-sm text-slate-300">
                  {result.company_fit.hiring_bar_advice}
                </p>
              </div>
            </Card>

            {/* Skills: Matched vs Gaps */}
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              {/* Matched Skills */}
              <Card title="Matched Skills" className={cardStyle}>
                <ul className="space-y-3">
                  {result.skill_analysis.matched_skills.map((s, idx) => (
                    <li key={idx} className="flex items-start justify-between border-b border-slate-800 pb-2">
                      <div>
                        <span className="font-medium text-emerald-400">{s.name}</span>
                        {s.evidence && (
                          <p className="text-xs text-slate-400">{s.evidence}</p>
                        )}
                      </div>
                      <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300 font-mono">
                        Level {s.level}/5
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>

              {/* Missing Gaps */}
              <Card title="Skill Gaps to Address" className={cardStyle}>
                <ul className="space-y-3">
                  {result.skill_analysis.missing_skills.map((s, idx) => (
                    <li key={idx} className="flex items-start justify-between border-b border-slate-800 pb-2">
                      <div>
                        <span className="font-medium text-amber-400">{s.name}</span>
                        {s.reason && (
                          <p className="text-xs text-slate-400">{s.reason}</p>
                        )}
                      </div>
                      <span className="rounded bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300 font-mono">
                        Target Lvl {s.target_level}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>

            {/* Resume Tips & Roadmap */}
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              <Card title="Resume Optimization Tips" className={cardStyle}>
                <ul className="list-disc space-y-2 pl-4 text-sm text-slate-300">
                  {result.resume_building_tips.map((tip, idx) => (
                    <li key={idx}>{tip}</li>
                  ))}
                </ul>
              </Card>

              <Card title="Next Technical Steps" className={cardStyle}>
                <ul className="list-disc space-y-2 pl-4 text-sm text-slate-300">
                  {result.learning_roadmap.map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ul>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}