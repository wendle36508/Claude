-- CreateTable
CREATE TABLE "Location" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "chain" TEXT NOT NULL,
    "address" TEXT NOT NULL,
    "city" TEXT NOT NULL,
    "state" TEXT NOT NULL,
    "lat" REAL NOT NULL,
    "lng" REAL NOT NULL,
    "scheduleNote" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "CheckIn" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "locationId" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "note" TEXT,
    "reporterName" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "CheckIn_locationId_fkey" FOREIGN KEY ("locationId") REFERENCES "Location" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE INDEX "CheckIn_locationId_createdAt_idx" ON "CheckIn"("locationId", "createdAt");
