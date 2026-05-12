import { buildCatalog } from "@/lib/tools/catalog";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const tools = buildCatalog();
  return Response.json({ tools, total: tools.length });
}
