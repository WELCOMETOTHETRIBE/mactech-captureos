import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const CLERK_JWT_TEMPLATE =
  process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE ?? "mactech";

/**
 * Multipart proxy for POST /sbir/decode/file.
 *
 * Forwards the raw FormData (containing the uploaded file) to the API with
 * the caller's Clerk JWT attached. Used by the SBIR form to decode topic
 * PDFs and attachment files into plain text before submitting the JSON
 * generate request.
 */
export async function POST(req: Request): Promise<Response> {
  const { getToken } = await auth();
  const token = await getToken({ template: CLERK_JWT_TEMPLATE });
  if (!token) {
    return NextResponse.json({ error: "not signed in" }, { status: 401 });
  }

  const formData = await req.formData();
  // Re-serialize: passing the original `req.body` through fetch can drop
  // the multipart boundary on some runtimes. Build a fresh FormData and
  // let undici set the boundary.
  const forwarded = new FormData();
  for (const [key, value] of formData.entries()) {
    forwarded.append(key, value);
  }

  const upstream = await fetch(`${API_BASE_URL}/sbir/decode/file`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: forwarded,
    cache: "no-store"
  });

  const text = await upstream.text();
  return new NextResponse(text, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store"
    }
  });
}
