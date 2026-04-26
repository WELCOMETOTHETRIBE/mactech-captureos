import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

/**
 * SSE proxy for /opportunities/{id}/ask/stream.
 *
 * Lives outside the `(app)` route group so the app shell doesn't try to
 * wrap a streaming response in HTML. Attaches the caller's Clerk JWT
 * server-side so the SAM/Anthropic key path stays off the browser, then
 * pipes the API's text/event-stream body straight back to the client.
 *
 * The middleware matcher already excludes paths under /api etc.; this
 * route is auth-gated by the in-handler `auth()` call.
 */
export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
): Promise<Response> {
  const { id } = await params;
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    return NextResponse.json(
      { error: "not signed in" },
      { status: 401 }
    );
  }

  // The browser POSTs JSON; forward verbatim.
  const body = await req.text();

  const upstream = await fetch(
    `${API_BASE_URL}/opportunities/${id}/ask/stream`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream"
      },
      body,
      cache: "no-store"
    }
  );

  if (!upstream.ok) {
    let detail: string;
    try {
      const j = (await upstream.json()) as { detail?: string };
      detail = j.detail ?? `API ${upstream.status}`;
    } catch {
      detail = `API ${upstream.status}`;
    }
    return NextResponse.json(
      { error: detail },
      { status: upstream.status }
    );
  }
  if (!upstream.body) {
    return NextResponse.json(
      { error: "upstream returned empty body" },
      { status: 502 }
    );
  }

  // Pipe the stream straight to the client. The same SSE format flows
  // through; the client component parses `data: ...\n\n` lines.
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
