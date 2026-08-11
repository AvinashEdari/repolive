import Link from "next/link";

import { Report, Results } from "../../analyze/page";
import styles from "../../analyze/results.module.css";
import MachineCheck from "./machine-check";

export default async function PublicAnalysisPage({
  params,
}: {
  params: Promise<{ publicId: string }>;
}) {
  const { publicId } = await params;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const response = await fetch(`${apiUrl}/api/v1/analyses/${encodeURIComponent(publicId)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    return <main className={styles.shell}><header><Link href="/">RepoLive.</Link></header>
      <section className={styles.search}><p>ANALYSIS UNAVAILABLE</p><h1>This analysis could not be found.</h1><Link href="/analyze">Analyze a repository</Link></section></main>;
  }
  const report = (await response.json()) as Report;
  return <main className={styles.shell}><header><Link href="/">RepoLive.</Link><Link href="/analyze">New analysis</Link></header><Results report={report}/><MachineCheck publicId={publicId}/></main>;
}
