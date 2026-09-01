import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { CHECK_IN_STATUSES } from "@/lib/types";

const VALID_STATUSES = new Set<string>(CHECK_IN_STATUSES);

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);

  if (!body || typeof body.locationId !== "string" || !VALID_STATUSES.has(body.status)) {
    return NextResponse.json({ error: "Invalid check-in payload" }, { status: 400 });
  }

  const location = await prisma.location.findUnique({ where: { id: body.locationId } });
  if (!location) {
    return NextResponse.json({ error: "Location not found" }, { status: 404 });
  }

  const checkIn = await prisma.checkIn.create({
    data: {
      locationId: body.locationId,
      status: body.status,
      note: typeof body.note === "string" && body.note.trim() ? body.note.trim().slice(0, 500) : null,
      reporterName:
        typeof body.reporterName === "string" && body.reporterName.trim()
          ? body.reporterName.trim().slice(0, 80)
          : null,
    },
  });

  return NextResponse.json({ checkIn }, { status: 201 });
}
