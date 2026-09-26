import { PrismaClient } from "@prisma/client";
import { DIRECTORY } from "./directory";

const prisma = new PrismaClient();

async function main() {
  for (const { slug, ...fields } of DIRECTORY) {
    await prisma.location.upsert({
      where: { slug },
      create: { slug, ...fields },
      update: fields,
    });
  }
  console.log(`Synced ${DIRECTORY.length} directory locations`);
}

main()
  .then(() => prisma.$disconnect())
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
