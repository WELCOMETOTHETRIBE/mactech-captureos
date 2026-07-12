import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

/**
 * Proxy for POST /sbir/topics/{id}/enrich. Forwards the Clerk JWT. The API
 * now enriches via DSIP's public API directly (seconds), falling back to
 * the Apify Playwright worker (up to ~90s) only if that fails — so we keep
 * a ~100s budget for the worst case.
 */
export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    return NextResponse.json({ error: "not signed in" }, { status: 401 });
  }
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 100_000);
  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/sbir/topics/${id}/enrich`, {
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
