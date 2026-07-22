import type { NextConfig } from "next";

const apiOrigin = (process.env.CRM_API_ORIGIN || "").replace(/\/$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  // Same-origin proxy for Cloud Run: browser → /backend/* → CRM_API_ORIGIN/*
  // Prefer NEXT_PUBLIC_API_URL pointing at the public API when uploads are large.
  async rewrites() {
    if (!apiOrigin) return [];
    return [
      {
        source: "/backend/:path*",
        destination: `${apiOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
