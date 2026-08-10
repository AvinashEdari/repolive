import type { Metadata } from "next";
import "./styles.css";
export const metadata: Metadata = { title: "RepoLive — Understand any repository", description: "Evidence-based repository analysis for everyone." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
