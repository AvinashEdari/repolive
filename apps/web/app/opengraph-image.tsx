import { ImageResponse } from "next/og";

export const alt = "RepoLive — evidence-based repository intelligence";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "center", padding: 80, background: "#080b0a", color: "#f4f7f3", fontFamily: "sans-serif" }}>
      <div style={{ color: "#a7f76b", fontSize: 34, fontWeight: 800 }}>RepoLive.</div>
      <div style={{ fontSize: 70, lineHeight: 1.05, fontWeight: 800, maxWidth: 980, marginTop: 35 }}>Understand a repository before you clone it.</div>
      <div style={{ fontSize: 28, color: "#a9b4ac", marginTop: 35 }}>Evidence-based analysis. Repository code is never executed.</div>
    </div>,
    size,
  );
}
