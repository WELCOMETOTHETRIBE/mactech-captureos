import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

/**
 * Auth-attached proxy for SBIR artifact downloads.
 * Path = submission UUID + the file's relative path inside the workspace
 * (e.g. `volume-5-supporting/01-pi-cv.md`). The Next dynamic segment
 * `[...path]` captures the multi-segment tail. The API enforces traversal
 * sandboxing — we only forward.
 */
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string; path: string[] }> }
) {
  const { id, path } = await params;
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    return NextResponse.redirect(
      new URL(`/sign-in?redirect_url=/sbir`, "http://localhost").toString(),
      302
    );
  }
  const rel = path.map((seg) => encodeURIComponent(seg)).join("/");
  const upstream = await fetch(
    `${API_BASE_URL}/sbir/submissions/${id}/files/${rel}`,
    {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store"
    }
  );
  if (!upstream.ok) {
    const text = await upstream.text();
    return NextResponse.json(
      { error: `API ${upstream.status}`, detail: text.slice(0, 400) },
      { status: upstream.status }
    );
  }
  const blob = await upstream.arrayBuffer();
  const ct =
    upstream.headers.get("content-type") ?? "application/octet-stream";
  const cd =
    upstream.headers.get("content-disposition") ??
    `attachment; filename="${path[path.length - 1] ?? "file"}"`;
  return new NextResponse(blob, {
    status: 200,
    headers: {
      "Content-Type": ct,
      "Content-Disposition": cd,
      "Cache-Control": "no-store"
    }
  });
}
