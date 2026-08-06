import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // emit a self-contained server bundle for a small production Docker image
  output: "standalone",
  turbopack: { root: __dirname },
};

export default nextConfig;
