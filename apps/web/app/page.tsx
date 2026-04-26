import Link from "next/link";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export default async function HomePage() {
  const { userId } = await auth();
  if (userId) redirect("/dashboard");

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <p className="text-xs uppercase tracking-wide text-neutral-500">MacTech CaptureOS</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">
        The operating system for defense contractors.
      </h1>
      <p className="mt-4 text-neutral-700">
        Identify, win, and stay eligible for federal work.
      </p>

      <div className="mt-8 flex gap-3">
        <Link
          href="/sign-in"
          className="rounded-md border border-neutral-900 bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
        >
          Sign in
        </Link>
        <Link
          href="/sign-up"
          className="rounded-md border border-neutral-300 px-4 py-2 text-sm text-neutral-700 hover:border-neutral-400"
        >
          Sign up
        </Link>
      </div>

      <footer className="mt-16 text-xs text-neutral-500">
        MacTech Solutions LLC · SDVOSB-certified · Veteran-Owned
      </footer>
    </main>
  );
}
