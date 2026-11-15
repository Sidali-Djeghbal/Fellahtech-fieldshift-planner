import type { NextConfig } from "next";

const isStaticExport = process.env.NEXT_OUTPUT_EXPORT === "true";

const nextConfig: NextConfig = {
  ...(isStaticExport ? { output: "export" } : {}),
  distDir: process.env.NEXT_DIST_DIR || ".next",
  images: {
    unoptimized: true,
  },
  ...(isStaticExport
    ? {}
    : {
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
      }),
};

export default nextConfig;
