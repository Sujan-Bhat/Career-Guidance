import Link from "next/link";

const FEATURES = [
  {
    tag: "FES ENGINE",
    title: "Focus Efficiency Score (FES)",
    desc: "Novel 5-metric cognitive calibration: TCR, session consistency, and resource depth.",
    gradient: "from-violet-500 to-indigo-600",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    tag: "HYBRID ML",
    title: "3-Stage Hybrid Cascade",
    desc: "Curriculum Knowledge Graph + FES Collaborative Filtering + Factorisation Machines.",
    gradient: "from-indigo-500 to-cyan-500",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  },
  {
    tag: "RL AGENT",
    title: "DQN Adaptive Feedback",
    desc: "17-dimensional state tracking with 8 adaptive policy actions evolving with your progress.",
    gradient: "from-cyan-500 to-teal-500",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
  },
  {
    tag: "ADVANCED AI",
    title: "AI Career Roadmaps",
    desc: "Interactive, roadmap.sh-style dynamic career milestones synthesized by Advanced Career Mind AI.",
    gradient: "from-purple-500 to-pink-500",
    icon: (
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
    ),
  },
];

export default function AuthShell({
  title,
  subtitle,
  activeTab = "login",
  children,
}: {
  title: string;
  subtitle: string;
  activeTab?: "login" | "register";
  children: React.ReactNode;
}) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#070A14] text-slate-100 selection:bg-violet-500 selection:text-white">
      {/* Ambient Lighting Orbs */}
      <div className="pointer-events-none absolute -top-40 -left-40 h-[600px] w-[600px] rounded-full bg-violet-600/15 blur-[140px]" />
      <div className="pointer-events-none absolute top-1/2 -right-40 h-[500px] w-[500px] rounded-full bg-cyan-500/10 blur-[130px]" />
      <div className="pointer-events-none absolute -bottom-40 left-1/3 h-[550px] w-[550px] rounded-full bg-indigo-600/15 blur-[150px]" />

      {/* Cyber Grid Texture */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: "radial-gradient(#ffffff 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />

      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col justify-between px-4 py-8 sm:px-6 lg:flex-row lg:items-center lg:gap-16 lg:px-8 lg:py-12">
        {/* Left Side: Brand Story & Architecture Showcase */}
        <div className="flex flex-1 flex-col justify-between py-4 lg:py-8">
          <div>
            {/* System Status Pill */}
            <div className="inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-3.5 py-1 text-xs font-medium text-violet-300 shadow-sm backdrop-blur-md">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
              </span>
              <span>CAREERMIND AI Engine · v2.4 Live</span>
            </div>

            {/* Hero Heading */}
            <h1 className="mt-6 text-3xl font-extrabold tracking-tight sm:text-4xl lg:text-5xl">
              <span className="block text-white">Behaviour-Aware</span>
              <span className="mt-1 block bg-gradient-to-r from-violet-400 via-indigo-300 to-cyan-400 bg-clip-text text-transparent">
                Adaptive Career Guidance
              </span>
            </h1>

            <p className="mt-4 max-w-lg text-sm leading-relaxed text-slate-400 sm:text-base">
              A closed feedback loop mapping cognitive engagement, quiz persistence, and resource depth
              into individualized learning trajectories and career milestones.
            </p>

            {/* Feature Cards Grid */}
            <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
              {FEATURES.map((item) => (
                <div
                  key={item.title}
                  className="group relative overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/40 p-4 transition-all duration-300 hover:border-slate-700 hover:bg-slate-900/70 hover:shadow-lg hover:shadow-violet-950/20"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${item.gradient} text-white shadow-md shadow-violet-500/20`}
                    >
                      {item.icon}
                    </div>
                    <div>
                      <span className="text-[10px] font-bold tracking-wider text-violet-400">
                        {item.tag}
                      </span>
                      <h3 className="text-xs font-semibold text-slate-200">
                        {item.title}
                      </h3>
                    </div>
                  </div>
                  <p className="mt-2 text-xs leading-normal text-slate-400">
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom Trust & Telemetry Bar */}
          <div className="mt-10 flex flex-wrap items-center gap-6 border-t border-slate-800/80 pt-6 text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span>200+ Student Profiles Seeded</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
              <span>18 Career Pathways Mapped</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-violet-400" />
              <span>PyTorch DQN Active</span>
            </div>
          </div>
        </div>

        {/* Right Side: Glassmorphic Auth Card */}
        <div className="w-full max-w-md shrink-0 py-6 lg:py-0">
          <div className="relative">
            {/* Radiant glow behind card */}
            <div className="absolute -inset-1 rounded-3xl bg-gradient-to-tr from-violet-600/30 via-indigo-600/20 to-cyan-500/30 opacity-70 blur-xl" />

            <div className="relative rounded-3xl border border-slate-800/90 bg-[#0E1526]/90 p-6 shadow-2xl backdrop-blur-2xl sm:p-8">
              {/* Integrated Tab Navigation Switcher */}
              <div className="mb-6 flex rounded-xl border border-slate-800 bg-slate-950/60 p-1">
                <Link
                  href="/login"
                  className={`flex-1 rounded-lg py-2 text-center text-xs font-semibold transition-all ${
                    activeTab === "login"
                      ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-md shadow-violet-600/25"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Sign In
                </Link>
                <Link
                  href="/register"
                  className={`flex-1 rounded-lg py-2 text-center text-xs font-semibold transition-all ${
                    activeTab === "register"
                      ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-md shadow-violet-600/25"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Create Account
                </Link>
              </div>

              {/* Header Title */}
              <div className="mb-6">
                <h2 className="text-xl font-bold tracking-tight text-white sm:text-2xl">
                  {title}
                </h2>
                <p className="mt-1 text-xs text-slate-400">
                  {subtitle}
                </p>
              </div>

              {/* Form Content */}
              {children}

              {/* Security Footer */}
              <div className="mt-6 flex items-center justify-center gap-1.5 border-t border-slate-800/80 pt-4 text-[11px] text-slate-500">
                <svg className="h-3.5 w-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <span>Encrypted JWT Sessions · Private & Anonymized</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
