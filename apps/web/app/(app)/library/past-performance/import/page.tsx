import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { importPastPerformanceFromPdf } from "@/lib/library-import";

export const dynamic = "force-dynamic";

export default function ImportPastPerformancePage() {
  return (
    <div className="space-y-6">
      <Link
        href="/library"
        className="text-xs text-neutral-500 hover:text-neutral-800"
      >
        ← Library
      </Link>

      <PageHeader
        eyebrow="Past performance"
        title="Import from PDF"
        subtitle={
          <span>
            Drop a prior-engagement write-up and Claude will extract the
            customer, period, contract value, and a clean narrative
            summary. You&rsquo;ll review on the next page before saving.
          </span>
        }
      />

      <div className="rounded-lg border border-neutral-200 bg-white p-6">
        <form
          action={importPastPerformanceFromPdf}
          encType="multipart/form-data"
          className="space-y-5"
        >
          <label
            htmlFor="pdf-file"
            className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-neutral-300 bg-neutral-50 px-6 py-12 text-center transition-colors hover:border-brand-500 hover:bg-brand-50"
          >
            <span className="text-base font-medium text-neutral-800">
              Drop a PDF here
            </span>
            <span className="mt-1 text-sm text-neutral-500">
              or click to browse · text or scanned PDFs · 20 MB max
            </span>
            <input
              id="pdf-file"
              name="file"
              type="file"
              accept="application/pdf,.pdf"
              required
              className="sr-only"
            />
          </label>

          <details className="rounded-md border border-neutral-200 bg-neutral-50 p-4 text-sm">
            <summary className="cursor-pointer text-neutral-700">
              What works best?
            </summary>
            <ul className="mt-3 list-disc space-y-1.5 pl-5 text-neutral-600">
              <li>
                Text-based PDFs (Word exports, govwide standard PWS docs)
                work best. Scanned PDFs and images are also supported via
                Tesseract OCR (English only) — quality depends on scan
                resolution.
              </li>
              <li>
                Past-performance write-ups, contract close-out memos, capture
                team&rsquo;s prior-engagement decks. Anything that reads like
                a citation.
              </li>
              <li>
                The AI looks for: customer agency + office, contract number,
                period of performance, contract value, NAICS, scope, tools,
                outcomes. Whatever&rsquo;s missing in the PDF will be left
                blank for you to fill in on the edit page.
              </li>
              <li>
                Generation takes 5–15 seconds. The page won&rsquo;t hang —
                just wait for the redirect.
              </li>
            </ul>
          </details>

          <div className="flex items-center justify-end gap-2 border-t border-neutral-200 pt-4">
            <Link
              href="/library"
              className="rounded-md border border-neutral-300 px-4 py-2 text-sm hover:border-neutral-500"
            >
              Cancel
            </Link>
            <button
              type="submit"
              className="rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
            >
              Import &amp; review →
            </button>
          </div>
        </form>
      </div>

      <p className="text-xs text-neutral-500">
        Prefer to type it in directly?{" "}
        <Link
          href="/library/past-performance/new"
          className="text-brand-700 hover:underline"
        >
          Use the manual form instead
        </Link>
        .
      </p>
    </div>
  );
}
