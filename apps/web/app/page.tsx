import Link from "next/link";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

/**
 * Marketing landing page — warm-paper, brand-teal, italic-serif title.
 * Phase 1 audience is the four named founders, who sign in directly; this
 * page exists for any unauthenticated visitor who lands on the root URL
 * before the Phase 4 marketing surface ships.
 */
export default async function HomePage() {
  const { userId } = await auth();
  if (userId) redirect("/dashboard");

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-3xl px-6 py-20">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
          MacTech CaptureOS
        </p>
        <h1 className="mt-3 text-4xl font-medium italic tracking-tight font-serif text-foreground leading-tight">
          The operating system for defense contractors.
        </h1>
        <p className="mt-5 max-w-xl text-base text-muted-foreground leading-relaxed">
          Identify, win, and stay eligible for federal work — capture
          intelligence, proposal automation, and CMMC readiness in one
          platform built by the team that uses it to win contracts themselves.
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/sign-in"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Sign in
          </Link>
          <Link
            href="/sign-up"
            className="inline-flex items-center justify-center rounded-md border border-input bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Sign up
          </Link>
        </div>

        <footer className="mt-20 text-xs text-muted-foreground">
          MacTech Solutions LLC · SDVOSB-certified · Veteran-Owned
        </footer>
      </div>
    </main>
  );
}
