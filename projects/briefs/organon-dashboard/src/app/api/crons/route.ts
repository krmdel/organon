import { listCronJobs } from "@/lib/crons/reader";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const jobs = listCronJobs();
  return Response.json({ jobs, total: jobs.length });
}
