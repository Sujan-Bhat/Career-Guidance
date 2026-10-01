import Link from "next/link";

const FEATURES = [
  {
    title: "Focus Efficiency Score",
    body: "A single weighted measure of how effectively you study.",
  },
  {
    title: "Hybrid recommendations",
    body: "Career pathways matched to your grades, skills and behaviour.",
  },
  {
    title: "Adaptive feedback",
    body: "RL-driven nudges that evolve with your progress.",
  },
];

export default function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <aside className="relative hidden w-1/2 flex-col justify-between bg-gradient-to-br from-primary via-primary-dark to-slate-900 p-10 text-white lg:flex">
        <Link href="/" className="text-xl font-bold tracking-wide">
          CAREERMIND
        </Link>
        <div>
          <h2 className="max-w-md text-3xl font-semibold leading-tight">
            Behaviour-aware career guidance, tuned to you.
          </h2>
          <ul className="mt-8 space-y-5">
            {FEATURES.map((feature) => (
              <li key={feature.title} className="flex gap-3">
                <span className="mt-1.5 h-2 w-2 flex-none rounded-full bg-white/80" />
                <div>
                  <p className="font-medium">{feature.title}</p>
                  <p className="text-sm text-white/70">{feature.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-white/50">
          Focus Efficiency Score · hybrid recommendations · RL feedback
        </p>
      </aside>
      <main className="flex w-full items-center justify-center bg-slate-50 px-4 py-12 lg:w-1/2">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <Link href="/" className="text-lg font-bold text-primary">
              CAREERMIND
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}
