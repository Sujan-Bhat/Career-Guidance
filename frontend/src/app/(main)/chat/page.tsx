"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

type Message = { role: "user" | "assistant"; content: string };

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");

  const send = () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: input }]);
    setInput("");
    // Phase 7: POST /api/v1/llm/chat via endpoints.llm.chat
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "Guidance responses arrive in Phase 7 (LLM gateway)." },
    ]);
  };

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Guidance Chat</h1>
      <Card className="flex min-h-[400px] flex-col">
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
          {messages.length === 0 && (
            <p className="text-sm text-slate-400">
              Ask about career pathways, courses, or how your Focus Efficiency Score is trending.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[80%] rounded px-3 py-2 text-sm ${
                m.role === "user" ? "self-end bg-primary text-white" : "self-start bg-slate-100"
              }`}
            >
              {m.content}
            </div>
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <input
            className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
            value={input}
            placeholder="Type your question..."
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <Button onClick={send}>Send</Button>
        </div>
      </Card>
    </div>
  );
}
