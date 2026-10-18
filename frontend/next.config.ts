import path from "node:path";

import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// The API token and backend address come from the repository's root .env, the same file the
// backend reads, so they are written once and always match.
loadEnvConfig(path.resolve(process.cwd(), ".."));

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
