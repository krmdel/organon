import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // The dashboard imports TypeScript source from
  // <organon-root>/mcp-servers/paper-search/src/* via the @paper-search/* path
  // alias in tsconfig.json. Next 16's bundler follows that alias at build time.
  //
  // Pin the workspace root explicitly so Turbopack stops auto-inferring it from
  // the parent lockfile (the Organon repo also keeps its own package-lock.json).
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
