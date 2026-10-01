"use client";

import { useId, useState } from "react";

type TextFieldProps = {
  label: string;
  error?: string | null;
  hint?: string;
  password?: boolean;
  className?: string;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "className" | "size">;

export default function TextField({
  label,
  error,
  hint,
  password = false,
  className = "",
  type,
  ...props
}: TextFieldProps) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const resolvedType = password ? (visible ? "text" : "password") : type;
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={resolvedType}
          className={`w-full rounded border bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 ${
            error
              ? "border-red-400 focus:ring-red-200"
              : "border-slate-300 focus:border-primary focus:ring-primary/20"
          } ${password ? "pr-16" : ""}`}
          {...props}
        />
        {password && (
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className="absolute inset-y-0 right-2 my-auto h-6 rounded px-2 text-xs font-medium text-primary hover:bg-primary-light"
          >
            {visible ? "Hide" : "Show"}
          </button>
        )}
      </div>
      {error ? (
        <p className="mt-1 text-xs text-red-600">{error}</p>
      ) : hint ? (
        <p className="mt-1 text-xs text-slate-400">{hint}</p>
      ) : null}
    </div>
  );
}
