import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

/**
 * SSE proxy for POST /sbir/generate/stream.
 *
 * Lives outside the (app) route group so the app shell doesn't try to wrap
 * a text/event-stream response in HTML. The browser posts the SBIRGenerateRequest
 * JSON; we forward it with the caller's Clerk JWT attached server-side and pipe
 * the API's stream straight back. Long-running: Standard depth can take 20+ min.
 */
export async function POST(req: Request): Promise<Response> {
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    return NextResponse.json({ error: "not signed in" }, { status: 401 });
  }

  const body = await req.text();
  const upstream = await fetch(`${API_BASE_URL}/sbir/generate/stream`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream"
    },
    body,
    cache: "no-store"
  });

  if (!upstream.ok) {
    let detail: string;
    try {
      const j = (await upstream.json()) as { detail?: string };
      detail = j.detail ?? `API ${upstream.status}`;
    } catch {
      detail = `API ${upstream.status}`;
    }
    return NextResponse.json({ error: detail }, { status: upstream.status });
  }
  if (!upstream.body) {
    return NextResponse.json(
      { error: "upstream returned empty body" },
      { status: 502 }
    );
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive"
    }
  });
}
