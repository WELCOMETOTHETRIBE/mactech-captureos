import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

export const metadata: Metadata = {
  title: "MacTech CaptureOS",
  description: "The operating system for defense contractors.",
  robots: { index: false, follow: false }
};

// This is an auth-gated SaaS app — every route reads request headers via
// Clerk's `auth()`. Prerendering doesn't apply, and forcing dynamic at the
// root layout propagates to every nested route including auto-generated
// /_not-found, avoiding "Dynamic server usage" build failures.
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-paper-50 text-neutral-900 antialiased">
        <ClerkProvider>{children}</ClerkProvider>
      </body>
    </html>
  );
}
