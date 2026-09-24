import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { TrackingProvider } from "@/lib/tracking/TrackingProvider";

export const metadata: Metadata = {
  title: "CAREERMIND",
  description: "Behaviour-aware adaptive career guidance platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <Providers>
          <TrackingProvider>{children}</TrackingProvider>
        </Providers>
      </body>
    </html>
  );
}
