-- CreateTable
CREATE TABLE "Haul" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "locationId" TEXT NOT NULL,
    "imagePath" TEXT NOT NULL,
    "caption" TEXT,
    "posterName" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Haul_locationId_fkey" FOREIGN KEY ("locationId") REFERENCES "Location" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE INDEX "Haul_locationId_createdAt_idx" ON "Haul"("locationId", "createdAt");

-- CreateIndex
CREATE INDEX "Haul_createdAt_idx" ON "Haul"("createdAt");
