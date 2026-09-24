import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6">
      <h1 className="text-4xl font-bold text-primary">CAREERMIND</h1>
      <p className="max-w-md text-center text-slate-600">
        Behaviour-aware adaptive career guidance: Focus Efficiency Score, hybrid
        recommendations, RL-based adaptive feedback, and career path prediction.
      </p>
      <div className="flex gap-4">
        <Link href="/login" className="rounded bg-primary px-5 py-2.5 text-white hover:bg-primary-dark">
          Login
        </Link>
        <Link
          href="/dashboard"
          className="rounded border border-slate-300 px-5 py-2.5 hover:bg-slate-100"
        >
          Dashboard
        </Link>
      </div>
    </main>
  );
}
