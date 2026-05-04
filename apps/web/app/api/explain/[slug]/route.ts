import { NextResponse } from "next/server";
import { apiFetch, type TermExplanationResponse } from "@/lib/api";

/**
 * Server proxy for /explain/{slug} so client components (TermPopover)
 * can lazily fetch a definition without us shipping the API base URL
 * or Clerk JWT to the browser.
 *
 * The hot path is a DB cache hit (sub-50ms), so we don't bother with
 * Next.js fetch caching here — apiFetch already runs server-side with
 * cache: "no-store" to honor tenant scoping.
 *
 * The popover sets `cache: "force-cache"` on its outgoing call which
 * lets the browser short-circuit identical re-requests for the same
 * slug within a session.
 */
export async function GET(
  _req: Request,
  ctx: { params: Promise<{ slug: string }> },
) {
  const { slug } = await ctx.params;
  if (!slug) {
    return NextResponse.json({ error: "missing slug" }, { status: 400 });
  }
  try {
    const data = await apiFetch<TermExplanationResponse>(
      `/explain/${encodeURIComponent(slug)}`,
    );
    return NextResponse.json(data, {
      // Tell the browser it's safe to reuse for the rest of the session;
      // the API itself rarely changes a definition.
      headers: { "Cache-Control": "private, max-age=300" },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "lookup failed";
    // Return 200 with a null payload so the popover can render a graceful
    // fallback ("couldn't load") rather than throwing in the UI thread.
    return NextResponse.json(
      { error: message },
      { status: message.includes("404") ? 404 : 502 },
    );
  }
}
