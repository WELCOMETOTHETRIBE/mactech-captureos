import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

/**
 * Proxy for POST /sbir/topics/refresh-dsip — pulls every open/pre-release
 * DoD SBIR/STTR topic with full content directly from dodsbirsttr.mil's
 * public API (no Apify, no LLM). Synchronous; typically 30–60s for ~70
 * topics. Returns {fetched, upserted, details_ok, elapsed_secs, error}.
 */
export async function POST(): Promise<Response> {
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    return NextResponse.json({ error: "not signed in" }, { status: 401 });
  }
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 150_000);
  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/sbir/topics/refresh-dsip`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
      cache: "no-store"
    });
  } catch (err) {
    return NextResponse.json(
      {
        error:
          err instanceof Error
            ? `proxy fetch failed: ${err.message}`
            : "proxy fetch failed"
      },
      { status: 504 }
    );
  } finally {
    clearTimeout(t);
  }
  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("content-type") ?? "application/json"
    }
  });
}
