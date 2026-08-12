import type { MetadataRoute } from "next";
import { siteUrl } from "../lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const paths = ["/analyze", "/tools", "/legal/privacy", "/legal/terms", "/legal/security", "/legal/acceptable-use", "/legal/contact"];
  return paths.map((path) => ({ url: new URL(path, siteUrl).toString() }));
}
