import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

export async function GET(req: NextRequest) {
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const qs = req.nextUrl.searchParams.toString();
  const url = `${API_BASE_URL}/tools/cyber-scope/feed/export.csv${qs ? `?${qs}` : ""}`;

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text();
    return NextResponse.json(
      { error: `API ${res.status} on feed CSV export`, detail: body.slice(0, 400) },
      { status: res.status }
    );
  }

  const text = await res.text();
  const disposition =
    res.headers.get("content-disposition") ?? 'attachment; filename="cyber-scope-feed.csv"';
  return new NextResponse(text, {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": disposition,
      "Cache-Control": "no-store",
    },
  });
}
