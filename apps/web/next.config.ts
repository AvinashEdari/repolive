import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  async redirects() {
    return [{ source: "/", destination: "/analyze", permanent: false }];
  },
};

export default nextConfig;
