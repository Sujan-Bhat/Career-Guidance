"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { endpoints } from "@/lib/api/client";

type Message = { role: "user" | "assistant"; content: string };

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    const text = input.trim();
    if (!text || pending) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setError(null);
    setPending(true);
    try {
      const { data } = await endpoints.llm.chat(text);
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (err) {
      const status = (err as { response?: { status?: number; data?: { detail?: string } } })
        .response?.status;
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(
        status === 503
          ? "The guidance assistant is not configured yet — set LLM_API_KEY on the backend."
          : detail || "The assistant is unavailable right now. Please try again."
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B1020] px-4 py-8 text-slate-100 sm:px-6">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
        <div>
          <p className="mb-2 text-sm font-medium text-violet-400">
            YOUR CAREER COMPANION
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Guidance Chat
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Explore career pathways, courses, and your Focus Efficiency Score.
          </p>
        </div>

        <Card className="flex min-h-[500px] flex-col !border !border-slate-800 !bg-[#111827] !shadow-xl !shadow-black/20">
          <div className="mb-4 flex items-center gap-3 border-b border-slate-800 pb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/15 text-lg text-violet-400">
              ✦
            </div>
            <div>
              <h2 className="font-semibold text-white">Career Assistant</h2>
              <p className="text-xs text-slate-400">
                Options, insights, and trade-offs
              </p>
            </div>
            <div className="ml-auto flex items-center gap-2 text-xs text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Assistant
            </div>
          </div>

          <div className="flex flex-1 flex-col gap-4 overflow-y-auto py-2">
            {messages.length === 0 && (
              <div className="rounded-xl border border-slate-800 bg-[#0B1020] p-5">
                <p className="mb-2 font-medium text-slate-200">
                  What would you like guidance on?
                </p>
                <p className="text-sm leading-6 text-slate-400">
                  Ask about career pathways, courses, or how your Focus
                  Efficiency Score is trending. The assistant presents options
                  and trade-offs — the career choice stays yours.
                </p>
              </div>
            )}

            {messages.map((m, i) => (
              <div
                key={i}
                className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ${
                  m.role === "user"
                    ? "self-end rounded-br-md border border-violet-500/30 bg-violet-600/20 text-violet-50"
                    : "self-start rounded-bl-md border border-slate-700 bg-slate-800/80 text-slate-200"
                }`}
              >
                {m.content}
              </div>
            ))}

            {pending && (
              <p className="self-start animate-pulse rounded-xl border border-slate-800 bg-slate-800/60 px-4 py-3 text-sm text-slate-400">
                Thinking…
              </p>
            )}

            {error && (
              <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-200">
                {error}
              </p>
            )}
          </div>

          <div className="mt-5 flex items-center gap-2 border-t border-slate-800 pt-4">
            <input
              className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-[#0B1020] px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 transition-colors focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20 disabled:opacity-50"
              value={input}
              placeholder="Ask about your career..."
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              disabled={pending}
            />

            <Button
              onClick={send}
              disabled={pending}
              className="!rounded-xl !border !border-teal-500 !bg-teal-700 !px-5 !py-3 !font-semibold !text-white !transition-all hover:!border-teal-400 hover:!bg-teal-600 disabled:!cursor-not-allowed disabled:!opacity-50"
            >
              {pending ? "…" : "Send"}
            </Button>
          </div>

          <p className="mt-3 text-center text-xs text-slate-500">
            Explore your options. Your career decisions remain yours.
          </p>
        </Card>
      </div>
    </div>
  );
}