
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

type ActiveQuiz = {
  quiz_id: string;
  title: string;
  skill: string;
  questions: Question[];
};

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

      track("resource_open", {
        resource_id: quizId,
        metadata: { resource_type: "quiz" },
      });

      setActive({ ...quiz, questions: quiz.questions ?? [] });
      setAnswers({});
      setResults(null);
    } catch (err) {
      const status = (err as {
        response?: { status?: number };
      }).response?.status;

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
      const response = (err as {
        response?: {
          status?: number;
          data?: { detail?: string };
        };
      }).response;

      setError(
        response?.status === 503
          ? "AI quiz generation needs LLM_API_KEY on the backend — or pick a demo quiz below."
          : response?.data?.detail || "Could not generate a quiz right now."
      );
    } finally {
      setGenerating(false);
    }
  };

  const postAttempt = async (
    quizId: string,
    itemId: string,
    selected: number
  ) => {
    track("quiz_attempt", {
      resource_id: quizId,
      metadata: { item_id: itemId, selected },
    });

    try {
      await endpoints.courses.quizAttempt(quizId, {
        item_id: itemId,
        selected,
      });
    } catch (err) {
      const response = (err as {
        response?: {
          status?: number;
          data?: { detail?: string };
        };
      }).response;

      if (
        response?.status === 400 &&
        (response.data?.detail ?? "").includes("active session")
      ) {
        await endpoints.collector.startSession();
        await endpoints.courses.quizAttempt(quizId, {
          item_id: itemId,
          selected,
        });
        return;
      }

      throw err;
    }
  };

  const submit = async () => {
    if (!active) return;

    setSubmitting(true);
    setError(null);

    track("task_start", {
      metadata: { quiz_id: active.quiz_id },
    });

    const outcome: Record<number, boolean> = {};

    try {
      for (let i = 0; i < active.questions.length; i += 1) {
        const selected = answers[i] === undefined ? -1 : answers[i];

        const correct =
          selected !== -1 &&
          selected === active.questions[i].answer;

        outcome[i] = correct;

        await postAttempt(active.quiz_id, `q${i}`, selected);
      }

      setResults(outcome);
    } catch (err) {
      const status = (err as {
        response?: { status?: number };
      }).response?.status;

      setError(
        status === 401 || status === 403
          ? "Login to record attempts (they feed your QAP score)."
          : status === 400
            ? "Attempts need an active tracked session — press Start (top-right) or reload after logging in."
            : "Could not record attempts."
      );

      setResults(outcome);
    } finally {
      track("task_complete", {
        metadata: { quiz_id: active.quiz_id },
      });

      closeResource("quiz_submitted");
      setSubmitting(false);
    }
  };

  const score =
    results !== null
      ? Object.values(results).filter(Boolean).length
      : null;

  const answeredAll =
    active !== null &&
    active.questions.every((_, i) => answers[i] !== undefined);

  return (
    <div className="flex flex-col gap-6 rounded-2xl bg-[#080d1b] p-4 text-slate-100 sm:p-6">
      <div className="space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-violet-400/20 bg-violet-500/10 px-3 py-1 text-xs font-semibold tracking-wide text-violet-300">
          <span className="h-1.5 w-1.5 rounded-full bg-violet-400" />
          LEARNING WORKSPACE
        </div>

        <h1 className="bg-gradient-to-r from-violet-200 via-purple-300 to-fuchsia-400 bg-clip-text text-3xl font-bold tracking-tight text-transparent sm:text-4xl">
          Skill Self-Assessment
        </h1>
      </div>

      <p className="max-w-3xl text-sm leading-6 text-slate-400 sm:text-base">
        Quizzes feed the Quiz Attempt Persistence (QAP) sub-metric and refresh
        your skill-assessment scores (which drive the recommender, RL state,
        and prediction ensemble).
      </p>

      {error && (
        <p className="rounded-xl border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm text-amber-200">
          {error}
        </p>
      )}

      {active ? (
        <div className="[&>div]:!border-slate-800 [&>div]:!bg-[#0f172a] [&>div]:!text-slate-100 [&>div]:!shadow-xl [&_h2]:!text-white [&_h3]:!text-white">
          <Card title={active.title}>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
              <span className="text-xs text-slate-400">
                {active.skill} · {active.questions.length} items

                {score !== null && (
                  <span className="ml-2 rounded-full border border-violet-400/30 bg-violet-500/10 px-2 py-1 font-semibold text-violet-200">
                    Score: {score}/{active.questions.length}
                  </span>
                )}
              </span>

              <Button
                variant="secondary"
                 className="bg-teal-700 text-white border border-teal-500
           hover:bg-teal-600 rounded-lg
           transition-all duration-200"
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
                <li
                  key={i}
                  className="rounded-xl border border-slate-800 bg-[#0b1223] p-4 sm:p-5"
                >
                  <p className="mb-3 text-sm font-semibold leading-6 text-slate-100">
                    {i + 1}. {q.question}
                  </p>

                  <div className="flex flex-col gap-1.5">
                    {q.options.map((opt, j) => {
                      const selected = answers[i] === j;
                      const revealed = results !== null;
                      const isCorrect = j === q.answer;
                      const wasRight = results?.[i];

                      let style =
                        "border-slate-700 bg-slate-900/60 text-slate-300 hover:border-violet-400/60 hover:bg-slate-800/80";

                      if (revealed && isCorrect) {
                        style =
                          "border-emerald-400/50 bg-emerald-400/10 text-emerald-200";
                      } else if (revealed && selected && !wasRight) {
                        style =
                          "border-rose-400/50 bg-rose-400/10 text-rose-200";
                      } else if (selected) {
                        style =
                          "border-violet-400 bg-violet-500/15 text-violet-100 ring-1 ring-violet-400/30";
                      }

                      return (
                        <label
                          key={j}
                          className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-3 text-sm transition ${style}`}
                        >
                          <input
                            className="h-4 w-4 accent-violet-500"
                            type="radio"
                            name={`q${i}`}
                            checked={selected}
                            disabled={results !== null || submitting}
                            onChange={() =>
                              setAnswers((prev) => ({
                                ...prev,
                                [i]: j,
                              }))
                            }
                          />

                          {opt}
                        </label>
                      );
                    })}
                  </div>

                  {results !== null && (
                    <p
                      className={`mt-2 text-xs font-medium ${
                        results[i]
                          ? "text-emerald-300"
                          : "text-rose-300"
                      }`}
                    >
                      {results[i]
                        ? "Correct"
                        : `Incorrect — correct answer: ${q.options[q.answer]}`}
                    </p>
                  )}
                </li>
              ))}
            </ol>

            <div className="mt-5 flex gap-3">
              {results === null && (
                <Button
                  onClick={submit}
                  disabled={!answeredAll || submitting}
                >
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
              <p className="mt-2 text-xs text-slate-400">
                Login first — attempts are recorded against your account and
                tracked session.
              </p>
            )}
          </Card>
        </div>
      ) : (
        <>
          <div className="[&>div]:!border-slate-800 [&>div]:!bg-[#0f172a] [&>div]:!text-slate-100 [&>div]:!shadow-xl [&_h2]:!text-white [&_h3]:!text-white">
            <Card title="Generate a quiz with AI">
              <div className="flex flex-wrap items-end gap-4">
                <label className="flex flex-col gap-2 text-sm font-medium text-slate-300">
                  Skill domain

                  <input
                    list="skill-options"
                    className="rounded-xl border border-slate-700 bg-[#080f20] px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-500/20"
                    value={aiSkill}
                    onChange={(e) => setAiSkill(e.target.value)}
                  />

                  <datalist id="skill-options">
                    {COMMON_SKILLS.map((s) => (
                      <option key={s} value={s} />
                    ))}
                  </datalist>
                </label>

                <label className="flex flex-col gap-2 text-sm font-medium text-slate-300">
                  Difficulty

                  <select
                    className="rounded-xl border border-slate-700 bg-[#080f20] px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-500/20"
                    value={aiDifficulty}
                    onChange={(e) =>
                      setAiDifficulty(Number(e.target.value))
                    }
                  >
                    <option value={1}>Basic</option>
                    <option value={2}>Intermediate</option>
                    <option value={3}>Advanced</option>
                  </select>
                </label>

                <label className="flex flex-col gap-2 text-sm font-medium text-slate-300">
                  Items

                  <select
                    className="rounded-xl border border-slate-700 bg-[#080f20] px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-violet-400 focus:ring-2 focus:ring-violet-500/20"
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

                <Button
                  onClick={generateQuiz}
                  disabled={generating || !aiSkill.trim()}
                >
                  {generating ? "Generating…" : "Generate"}
                </Button>
              </div>
            </Card>
          </div>

          <div className="[&>div]:!border-slate-800 [&>div]:!bg-[#0f172a] [&>div]:!text-slate-100 [&>div]:!shadow-xl [&_h2]:!text-white [&_h3]:!text-white">
            <Card title="Demo quizzes">
              {isLoading && (
                <p className="py-3 text-sm text-slate-400">
                  Loading quizzes…
                </p>
              )}

              {listError && (
                <p className="rounded-xl border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-sm text-rose-200">
                  Quiz list unavailable — try again.
                </p>
              )}

              {data && quizzes.length === 0 && (
                <p className="max-w-3xl text-sm leading-6 text-slate-400 sm:text-base">
                  No quizzes yet — run{" "}
                  <code className="rounded bg-slate-800 px-1.5 py-1 text-violet-200">
                    python data/seeds/seed_mongo.py --skip-students
                  </code>{" "}
                  or generate one above.
                </p>
              )}

              <div className="flex flex-col gap-3">
                {quizzes.map((quiz) => (
                  <div
                    key={quiz.quiz_id}
                    className="group flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-[#0b1223] px-4 py-3 transition hover:border-violet-400/40 hover:bg-slate-900/80"
                  >
                    <div>
                      <p className="text-sm font-medium text-slate-100 transition group-hover:text-violet-200">
                        {quiz.title}
                      </p>

                      <p className="text-xs text-slate-400">
                        {quiz.skill} · {quiz.item_count} items
                      </p>
                    </div>

                    <Button
                     className="bg-teal-700 text-white border border-teal-500
           hover:bg-teal-600 rounded-lg
           transition-all duration-200"
                      onClick={() => openQuiz(quiz.quiz_id)}
                    >
                      Start
                    </Button>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
