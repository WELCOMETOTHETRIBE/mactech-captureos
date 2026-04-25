import Link from "next/link";

export const dynamic = "force-dynamic";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-xl px-6 py-24 text-center">
      <p className="text-xs uppercase tracking-wide text-neutral-500">404</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="mt-4 text-sm text-neutral-600">
        That route doesn&rsquo;t exist in MacTech CaptureOS.
      </p>
      <Link
        href="/"
        className="mt-6 inline-block rounded-md border border-neutral-300 px-4 py-2 text-sm hover:border-neutral-400"
      >
        Back to start
      </Link>
    </main>
  );
}
