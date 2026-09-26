-- AlterTable
ALTER TABLE "Location" ADD COLUMN     "hours" TEXT,
ADD COLUMN     "slug" TEXT;

-- CreateIndex
CREATE UNIQUE INDEX "Location_slug_key" ON "Location"("slug");

