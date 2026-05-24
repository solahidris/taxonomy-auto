import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    outputFileTracingExcludes: {
      // Exclude large binary/raw files that API routes never read.
      // .npy embeddings (~136 MB), .jsonl raw video dumps (~20 MB), .pkl graphs.
      "*": [
        "data/**/*.npy",
        "data/**/*.jsonl",
        "data/**/*.pkl",
      ],
    },
  },
};

export default nextConfig;
