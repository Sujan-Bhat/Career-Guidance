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
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Guidance Chat</h1>
      <Card className="flex min-h-[400px] flex-col">
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
          {messages.length === 0 && (
            <p className="text-sm text-slate-400">
              Ask about career pathways, courses, or how your Focus Efficiency Score is trending.
              The assistant presents options and trade-offs — the career choice stays yours.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[80%] whitespace-pre-wrap rounded px-3 py-2 text-sm ${
                m.role === "user" ? "self-end bg-primary text-white" : "self-start bg-slate-100"
              }`}
            >
              {m.content}
            </div>
          ))}
          {pending && (
            <p className="self-start text-sm text-slate-400">Thinking…</p>
          )}
          {error && (
            <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {error}
            </p>
          )}
        </div>
        <div className="mt-4 flex gap-2">
          <input
            className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
            value={input}
            placeholder="Type your question..."
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            disabled={pending}
          />
          <Button onClick={send} disabled={pending}>
            {pending ? "…" : "Send"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
