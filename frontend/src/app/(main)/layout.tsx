
import AppNav from "@/components/AppNav";

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-[#0B1020] text-slate-100 lg:flex-row">
      <AppNav />

      <main className="min-w-0 flex-1 bg-[#0B1020] p-4 sm:p-6 lg:p-8">
        {children}
      </main>
    </div>
  );
}
