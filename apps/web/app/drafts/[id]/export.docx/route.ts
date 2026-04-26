import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

/**
 * Proxies the API's binary DOCX response with the caller's Clerk session
 * attached as a Bearer token. Native <a href="..."> downloads can't
 * carry an Authorization header, so the link target is this route which
 * authenticates via the same Clerk session cookie.
 *
 * Lives at /drafts/[id]/export.docx (outside the (app) group so the
 * layout shell — sidebar, header — doesn't wrap a binary response).
 */
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    return NextResponse.redirect(
      new URL(`/sign-in?redirect_url=/drafts/${id}`, "http://localhost").toString(),
      302
    );
  }

  const res = await fetch(`${API_BASE_URL}/drafts/${id}/export.docx`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store"
  });

  if (!res.ok) {
    const body = await res.text();
    return NextResponse.json(
      {
        error: `API ${res.status} on /drafts/${id}/export.docx`,
        detail: body.slice(0, 400)
      },
      { status: res.status }
    );
  }

  // Stream the binary back to the client with the API's Content-Disposition.
  const blob = await res.arrayBuffer();
  const disposition =
    res.headers.get("content-disposition") ??
    `attachment; filename="draft-${id}.docx"`;
  return new NextResponse(blob, {
    status: 200,
    headers: {
      "Content-Type":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "Content-Disposition": disposition,
      "Cache-Control": "no-store"
    }
  });
}
