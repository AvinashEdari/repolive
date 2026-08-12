import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analyze a public repository",
  description: "Create a bounded, deterministic report for a public GitHub repository.",
  alternates: { canonical: "/analyze" },
};

export default function AnalyzeLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
