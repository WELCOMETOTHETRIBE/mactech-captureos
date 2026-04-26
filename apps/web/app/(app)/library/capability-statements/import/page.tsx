import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { importCapabilityStatementFromPdf } from "@/lib/library-import";

export const dynamic = "force-dynamic";

export default function ImportCapabilityStatementPage() {
  return (
    <div className="space-y-6">
      <Link
        href="/library"
        className="text-xs text-neutral-500 hover:text-neutral-800"
      >
        ← Library
      </Link>

      <PageHeader
        eyebrow="Capability statements"
        title="Import from PDF"
        subtitle={
          <span>
            Drop a capability deck or marketing one-pager and Claude will
            extract a structured capability cluster — title, summary, NAICS
            codes, and keywords. You&rsquo;ll review on the next page before
            saving.
          </span>
        }
      />

      <div className="rounded-lg border border-neutral-200 bg-white p-6">
        <form
          action={importCapabilityStatementFromPdf}
          encType="multipart/form-data"
          className="space-y-5"
        >
          <label
            htmlFor="cs-pdf-file"
            className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-neutral-300 bg-neutral-50 px-6 py-12 text-center transition-colors hover:border-brand-500 hover:bg-brand-50"
          >
            <span className="text-base font-medium text-neutral-800">
              Drop a capability statement PDF here
            </span>
            <span className="mt-1 text-sm text-neutral-500">
              or click to browse · text or scanned PDFs · 20 MB max
            </span>
            <input
              id="cs-pdf-file"
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
                Text-based PDFs are the highest-fidelity — capability
                decks, one-pagers, the "About" section of a proposal
                narrative. Scanned PDFs and images are also supported
                via Tesseract OCR (English only).
              </li>
              <li>
                One PDF = one capability cluster. If your deck describes 3
                separate capability areas, run the import three times with
                trimmed PDFs (one per area) for cleaner extraction.
              </li>
              <li>
                The AI looks for: cluster name, scope summary, frameworks/
                tools/standards (e.g. NIST 800-53, FedRAMP, CMMC, RMF, eMASS),
                applicable NAICS codes, and which founder owns the area if
                stated. Whatever&rsquo;s missing in the PDF gets left blank
                for you to fill in on the edit page.
              </li>
              <li>
                After save, the embed worker generates a vector embedding
                within 15 minutes — at that point this capability is live in
                the opportunity scoring engine.
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
          href="/library/capability-statements/new"
          className="text-brand-700 hover:underline"
        >
          Use the manual form instead
        </Link>
        .
      </p>
    </div>
  );
}
