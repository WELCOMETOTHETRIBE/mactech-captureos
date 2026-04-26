import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

/**
 * Polled by the import-job page. Proxies GET /library/import/jobs/{id}
 * with the caller's Clerk JWT attached. Lives outside the (app) group
 * so the polling client doesn't pull the layout shell over the wire.
 */
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    return NextResponse.json(
      { error: "not signed in" },
      { status: 401 }
    );
  }

  const res = await fetch(
    `${API_BASE_URL}/library/import/jobs/${id}`,
    {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store"
    }
  );

  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: {
      "Content-Type":
        res.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store"
    }
  });
}
