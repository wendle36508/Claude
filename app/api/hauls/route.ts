import { NextResponse } from "next/server";
import { mkdir, writeFile } from "fs/promises";
import path from "path";
import { randomUUID } from "crypto";
import { prisma } from "@/lib/db";

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const EXTENSION_BY_MIME: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
  "image/gif": "gif",
};

const UPLOAD_DIR = path.join(process.cwd(), "public", "uploads", "hauls");

export async function POST(request: Request) {
  const form = await request.formData().catch(() => null);
  if (!form) {
    return NextResponse.json({ error: "Invalid form data" }, { status: 400 });
  }

  const locationId = form.get("locationId");
  const image = form.get("image");
  const caption = form.get("caption");
  const posterName = form.get("posterName");

  if (typeof locationId !== "string" || !locationId) {
    return NextResponse.json({ error: "Missing locationId" }, { status: 400 });
  }
  if (!(image instanceof File) || image.size === 0) {
    return NextResponse.json({ error: "Missing image" }, { status: 400 });
  }

  const extension = EXTENSION_BY_MIME[image.type];
  if (!extension) {
    return NextResponse.json({ error: "Unsupported image type" }, { status: 400 });
  }
  if (image.size > MAX_IMAGE_BYTES) {
    return NextResponse.json({ error: "Image too large (max 8MB)" }, { status: 400 });
  }

  const location = await prisma.location.findUnique({ where: { id: locationId } });
  if (!location) {
    return NextResponse.json({ error: "Location not found" }, { status: 404 });
  }

  await mkdir(UPLOAD_DIR, { recursive: true });

  // Never trust the client-supplied filename — generate our own.
  const filename = `${randomUUID()}.${extension}`;
  const bytes = Buffer.from(await image.arrayBuffer());
  await writeFile(path.join(UPLOAD_DIR, filename), bytes);

  const haul = await prisma.haul.create({
    data: {
      locationId,
      imagePath: `/uploads/hauls/${filename}`,
      caption: typeof caption === "string" && caption.trim() ? caption.trim().slice(0, 500) : null,
      posterName:
        typeof posterName === "string" && posterName.trim() ? posterName.trim().slice(0, 80) : null,
    },
  });

  return NextResponse.json({ haul }, { status: 201 });
}
