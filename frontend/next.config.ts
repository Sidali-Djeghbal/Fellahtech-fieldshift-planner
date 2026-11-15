import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    unoptimized: true,
  },
  async rewrites() {
    const upstream = process.env.API_UPSTREAM_URL || "http://localhost:8000";
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
    const apiRewrites =
      apiBase && apiBase.startsWith("http")
        ? []
        : [
            {
              source: "/api/v1/:path*",
              destination: `${upstream}/api/v1/:path*`,
            },
          ];
    return {
      afterFiles: apiRewrites,
      fallback: [],
    };
  },
};

export default nextConfig;
