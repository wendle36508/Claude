import { NextResponse } from "next/server";
import { mkdir, writeFile } from "fs/promises";
import path from "path";
import { randomUUID } from "crypto";
import { put } from "@vercel/blob";
import { prisma } from "@/lib/db";

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const EXTENSION_BY_MIME: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
  "image/gif": "gif",
};

const UPLOAD_DIR = path.join(process.cwd(), "public", "uploads", "hauls");

/**
 * Vercel's filesystem is ephemeral per-request, so local disk only works
 * for local dev. In production (BLOB_READ_WRITE_TOKEN set, which a
 * Vercel Blob store injects automatically) uploads go to Blob storage
 * instead — same call site, no other code needs to know which one ran.
 */
async function storeImage(image: File, filename: string): Promise<string> {
  if (process.env.BLOB_READ_WRITE_TOKEN) {
    const blob = await put(`hauls/${filename}`, image, { access: "public" });
    return blob.url;
  }

  await mkdir(UPLOAD_DIR, { recursive: true });
  const bytes = Buffer.from(await image.arrayBuffer());
  await writeFile(path.join(UPLOAD_DIR, filename), bytes);
  return `/uploads/hauls/${filename}`;
}

export async function POST(request: Request) {
  const form = await request.formData().catch(() => null);
  if (!form) {
    return NextResponse.json({ error: "Invalid form data" }, { status: 400 });
  }

  const locationId = form.get("locationId");
  const image = form.get("image");
  const caption = form.get("caption");
  const posterName = form.get("posterName");
  const forSale = form.get("forSale") === "true";
  const sellerHandle = form.get("sellerHandle");
  const priceRaw = form.get("price");

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

  let sellerId: string | null = null;
  let price: number | null = null;
  if (forSale) {
    if (typeof sellerHandle !== "string" || !sellerHandle.trim()) {
      return NextResponse.json({ error: "Seller handle is required to list for sale" }, { status: 400 });
    }
    const seller = await prisma.seller.findUnique({ where: { handle: sellerHandle.toLowerCase().trim() } });
    if (!seller) {
      return NextResponse.json(
        { error: "No seller profile with that handle — claim one at /market/new first" },
        { status: 404 }
      );
    }
    sellerId = seller.id;

    price = typeof priceRaw === "string" ? Number(priceRaw) : NaN;
    if (!Number.isFinite(price) || price <= 0) {
      return NextResponse.json({ error: "Enter a valid price" }, { status: 400 });
    }
  }

  // Never trust the client-supplied filename — generate our own.
  const filename = `${randomUUID()}.${extension}`;
  const imagePath = await storeImage(image, filename);

  const haul = await prisma.haul.create({
    data: {
      locationId,
      imagePath,
      caption: typeof caption === "string" && caption.trim() ? caption.trim().slice(0, 500) : null,
      posterName:
        typeof posterName === "string" && posterName.trim() ? posterName.trim().slice(0, 80) : null,
      forSale,
      sellerId,
      price,
    },
  });

  return NextResponse.json({ haul }, { status: 201 });
}
