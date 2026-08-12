import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Repository tools",
  description:
    "Diagnose setup errors, compare analyzed repositories, and discover public GitHub projects.",
};

export default function ToolsLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
