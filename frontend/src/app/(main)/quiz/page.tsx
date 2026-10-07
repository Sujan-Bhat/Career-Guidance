"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { endpoints, isLoggedIn } from "@/lib/api/client";
import { useTracking } from "@/lib/tracking/TrackingProvider";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

type QuizListItem = {
  quiz_id: string;
  title: string;
  skill: string;
  item_count: number;
};
type Question = {
  question: string;
  options: string[];
  answer: number;
  difficulty?: number;
};
type ActiveQuiz = { quiz_id: string; title: string; skill: string; questions: Question[] };

const COMMON_SKILLS = [
  "dsa",
  "programming_python",
  "programming_java",
  "databases_sql",
  "ml_fundamentals",
  "electronics_digital",
  "operating_systems",
  "networks",
];

export default function QuizPage() {
  const loggedIn = isLoggedIn();
  const { track, closeResource } = useTracking();
  const [active, setActive] = useState<ActiveQuiz | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [results, setResults] = useState<Record<number, boolean> | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [aiSkill, setAiSkill] = useState("programming_python");
  const [aiDifficulty, setAiDifficulty] = useState(2);
  const [aiItems, setAiItems] = useState(5);
  const [generating, setGenerating] = useState(false);

  const { data, isLoading, error: listError } = useQuery({
    queryKey: ["quizzes"],
    queryFn: () => endpoints.courses.quizzes(),
  });
  const quizzes: QuizListItem[] = data?.data?.quizzes ?? [];

  const openQuiz = async (quizId: string) => {
    setError(null);
    try {
      const { data: quiz } = await endpoints.courses.quiz(quizId);
      track("resource_open", { resource_id: quizId, metadata: { resource_type: "quiz" } });
      setActive({ ...quiz, questions: quiz.questions ?? [] });
      setAnswers({});
      setResults(null);
    } catch (err) {
      const status = (err as { response?: { status?: number } }).response?.status;
      setError(
        status === 401 || status === 403
          ? "Login to take quizzes — attempts are recorded against your tracked session."
          : "Quiz unavailable."
      );
    }
  };

  const generateQuiz = async () => {
    if (!aiSkill.trim() || generating) return;
    setGenerating(true);
    setError(null);
    try {
      const { data: payload } = await endpoints.llm.quizGenerate({
        skill: aiSkill.trim(),
        difficulty: aiDifficulty,
        n_items: aiItems,
      });
      track("resource_open", {
        resource_id: payload.quiz_id,
        metadata: { resource_type: "quiz" },
      });
      setActive({
        quiz_id: payload.quiz_id,
        title: `AI quiz: ${payload.skill}`,
        skill: payload.skill,
        questions: payload.items ?? [],
      });
      setAnswers({});
      setResults(null);
    } catch (err) {
      const response = (err as { response?: { status?: number; data?: { detail?: string } } }).response;
      setError(
        response?.status === 503
          ? "AI quiz generation needs LLM_API_KEY on the backend — or pick a demo quiz below."
          : response?.data?.detail || "Could not generate a quiz right now."
      );
    } finally {
      setGenerating(false);
    }
  };

  const postAttempt = async (quizId: string, itemId: string, selected: number) => {
    track("quiz_attempt", { resource_id: quizId, metadata: { item_id: itemId, selected } });
    try {
      await endpoints.courses.quizAttempt(quizId, { item_id: itemId, selected });
    } catch (err) {
      const response = (err as { response?: { status?: number; data?: { detail?: string } } }).response;
      if (response?.status === 400 && (response.data?.detail ?? "").includes("active session")) {
        await endpoints.collector.startSession(); // ensure a tracked session exists
        await endpoints.courses.quizAttempt(quizId, { item_id: itemId, selected });
        return;
      }
      throw err;
    }
  };

  const submit = async () => {
    if (!active) return;
    setSubmitting(true);
    setError(null);
    track("task_start", { metadata: { quiz_id: active.quiz_id } });
    const outcome: Record<number, boolean> = {};
    try {
      for (let i = 0; i < active.questions.length; i += 1) {
        const selected = answers[i] === undefined ? -1 : answers[i];
        const correct = selected !== -1 && selected === active.questions[i].answer;
        outcome[i] = correct;
        await postAttempt(active.quiz_id, `q${i}`, selected);
      }
      setResults(outcome);
    } catch (err) {
      const status = (err as { response?: { status?: number } }).response?.status;
      setError(
        status === 401 || status === 403
          ? "Login to record attempts (they feed your QAP score)."
          : status === 400
          ? "Attempts need an active tracked session — press Start (top-right) or reload after logging in."
          : "Could not record attempts."
      );
      setResults(outcome); // still show local scoring for what got through
    } finally {
      track("task_complete", { metadata: { quiz_id: active.quiz_id } });
      // the attempt stream is over: close the visit so its dwell covers the
      // working time (a resource_close is required for DFET/LRDS to see it)
      closeResource("quiz_submitted");
      setSubmitting(false);
    }
  };

  const score =
    results !== null
      ? Object.values(results).filter(Boolean).length
      : null;
  const answeredAll =
    active !== null && active.questions.every((_, i) => answers[i] !== undefined);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Skill Self-Assessment</h1>
      <p className="text-sm text-slate-500">
        Quizzes feed the Quiz Attempt Persistence (QAP) sub-metric and refresh your
        skill-assessment scores (which drive the recommender, RL state, and prediction ensemble).
      </p>

      {error && (
        <p className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error}
        </p>
      )}

      {active ? (
        <Card title={active.title}>
          <div className="mb-4 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {active.skill} · {active.questions.length} items
              {score !== null && (
                <span className="ml-2 font-semibold text-slate-700">
                  Score: {score}/{active.questions.length}
                </span>
              )}
            </span>
            <Button
              variant="secondary"
              onClick={() => {
                closeResource("quiz_exit");
                setActive(null);
                setAnswers({});
                setResults(null);
                setError(null);
              }}
            >
              Back to quizzes
            </Button>
          </div>

          <ol className="flex flex-col gap-5">
            {active.questions.map((q, i) => (
              <li key={i}>
                <p className="mb-2 text-sm font-medium text-slate-800">
                  {i + 1}. {q.question}
                </p>
                <div className="flex flex-col gap-1.5">
                  {q.options.map((opt, j) => {
                    const selected = answers[i] === j;
                    const revealed = results !== null;
                    const isCorrect = j === q.answer;
                    const wasRight = results?.[i];
                    let style = "border-slate-200 hover:border-slate-300";
                    if (revealed && isCorrect) style = "border-green-300 bg-green-50";
                    else if (revealed && selected && !wasRight) style = "border-red-300 bg-red-50";
                    else if (selected) style = "border-primary bg-primary/5";
                    return (
                      <label
                        key={j}
                        className={`flex cursor-pointer items-center gap-2 rounded border px-3 py-2 text-sm text-slate-700 ${style}`}
                      >
                        <input
                          type="radio"
                          name={`q${i}`}
                          checked={selected}
                          disabled={results !== null || submitting}
                          onChange={() => setAnswers((prev) => ({ ...prev, [i]: j }))}
                        />
                        {opt}
                      </label>
                    );
                  })}
                </div>
                {results !== null && (
                  <p className={`mt-1 text-xs ${results[i] ? "text-green-700" : "text-red-600"}`}>
                    {results[i] ? "Correct" : `Incorrect — correct answer: ${q.options[q.answer]}`}
                  </p>
                )}
              </li>
            ))}
          </ol>

          <div className="mt-5 flex gap-3">
            {results === null && (
              <Button onClick={submit} disabled={!answeredAll || submitting}>
                {submitting ? "Recording…" : "Submit attempts"}
              </Button>
            )}
            {results !== null && (
              <Button
                variant="secondary"
                onClick={() => {
                  track("resource_open", {
                    resource_id: active.quiz_id,
                    metadata: { resource_type: "quiz" },
                  });
                  setAnswers({});
                  setResults(null);
                }}
              >
                Retake
              </Button>
            )}
          </div>
          {!loggedIn && results === null && (
            <p className="mt-2 text-xs text-slate-500">
              Login first — attempts are recorded against your account and tracked session.
            </p>
          )}
        </Card>
      ) : (
        <>
          <Card title="Generate a quiz with AI">
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-xs text-slate-600">
                Skill domain
                <input
                  list="skill-options"
                  className="rounded border border-slate-300 px-2 py-1.5 text-sm"
                  value={aiSkill}
                  onChange={(e) => setAiSkill(e.target.value)}
                />
                <datalist id="skill-options">
                  {COMMON_SKILLS.map((s) => (
                    <option key={s} value={s} />
                  ))}
                </datalist>
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-600">
                Difficulty
                <select
                  className="rounded border border-slate-300 px-2 py-1.5 text-sm"
                  value={aiDifficulty}
                  onChange={(e) => setAiDifficulty(Number(e.target.value))}
                >
                  <option value={1}>Basic</option>
                  <option value={2}>Intermediate</option>
                  <option value={3}>Advanced</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-slate-600">
                Items
                <select
                  className="rounded border border-slate-300 px-2 py-1.5 text-sm"
                  value={aiItems}
                  onChange={(e) => setAiItems(Number(e.target.value))}
                >
                  {[3, 5, 8].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <Button onClick={generateQuiz} disabled={generating || !aiSkill.trim()}>
                {generating ? "Generating…" : "Generate"}
              </Button>
            </div>
          </Card>

          <Card title="Demo quizzes">
            {isLoading && <p className="text-sm text-slate-400">Loading quizzes…</p>}
            {listError && (
              <p className="text-sm text-red-600">Quiz list unavailable — try again.</p>
            )}
            {data && quizzes.length === 0 && (
              <p className="text-sm text-slate-500">
                No quizzes yet — run <code>python data/seeds/seed_mongo.py --skip-students</code>{" "}
                or generate one above.
              </p>
            )}
            <div className="flex flex-col gap-3">
              {quizzes.map((quiz) => (
                <div
                  key={quiz.quiz_id}
                  className="flex items-center justify-between rounded border border-slate-100 px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-800">{quiz.title}</p>
                    <p className="text-xs text-slate-500">
                      {quiz.skill} · {quiz.item_count} items
                    </p>
                  </div>
                  <Button variant="secondary" onClick={() => openQuiz(quiz.quiz_id)}>
                    Start
                  </Button>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
