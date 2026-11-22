import type { NextConfig } from "next";
import { backendOrigin } from "./src/lib/backend-origin";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendOrigin()}/api/:path*` }];
  },
};

export default nextConfig;
