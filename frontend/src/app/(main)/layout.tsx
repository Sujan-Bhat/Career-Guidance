import Link from "next/link";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/recommendations", label: "Recommendations" },
  { href: "/prediction", label: "Career Prediction" },
  { href: "/quiz", label: "Quizzes" },
  { href: "/chat", label: "Guidance Chat" },
];

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <nav className="flex w-56 flex-col gap-1 border-r border-slate-200 bg-white p-4">
        <Link href="/" className="mb-4 px-2 text-lg font-bold text-primary">
          CAREERMIND
        </Link>
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded px-2 py-2 text-sm text-slate-700 hover:bg-primary-light"
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}
