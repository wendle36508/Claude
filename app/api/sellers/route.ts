import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { isValidHandle } from "@/lib/handle";

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);

  if (!body || typeof body.handle !== "string" || typeof body.displayName !== "string") {
    return NextResponse.json({ error: "Missing handle or display name" }, { status: 400 });
  }

  const handle = body.handle.toLowerCase().trim();
  const displayName = body.displayName.trim().slice(0, 80);

  if (!isValidHandle(handle)) {
    return NextResponse.json(
      { error: "Handle must be 3-30 characters: lowercase letters, numbers, hyphens" },
      { status: 400 }
    );
  }
  if (!displayName) {
    return NextResponse.json({ error: "Display name is required" }, { status: 400 });
  }

  const existing = await prisma.seller.findUnique({ where: { handle } });
  if (existing) {
    return NextResponse.json({ error: "That handle is already taken" }, { status: 409 });
  }

  const seller = await prisma.seller.create({
    data: {
      handle,
      displayName,
      bio: typeof body.bio === "string" && body.bio.trim() ? body.bio.trim().slice(0, 300) : null,
      contactLink:
        typeof body.contactLink === "string" && body.contactLink.trim()
          ? body.contactLink.trim().slice(0, 300)
          : null,
    },
  });

  return NextResponse.json({ seller }, { status: 201 });
}
