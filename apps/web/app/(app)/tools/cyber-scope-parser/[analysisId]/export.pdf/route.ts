import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ analysisId: string }> }
) {
  const { analysisId } = await params;
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const res = await fetch(
    `${API_BASE_URL}/tools/cyber-scope/analyses/${analysisId}/export.pdf`,
    {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    }
  );

  if (!res.ok) {
    const body = await res.text();
    return NextResponse.json(
      {
        error: `API ${res.status} on cyber scope PDF export`,
        detail: body.slice(0, 400),
      },
      { status: res.status }
    );
  }

  const blob = await res.arrayBuffer();
  const disposition =
    res.headers.get("content-disposition") ??
    `attachment; filename="cyber-scope-${analysisId}.pdf"`;
  return new NextResponse(blob, {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": disposition,
      "Cache-Control": "no-store",
    },
  });
}
