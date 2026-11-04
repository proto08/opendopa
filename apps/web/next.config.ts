import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // workspace の共有パッケージ(TS のまま公開している)をビルドに含める
  transpilePackages: ["@opendopa/shared"],
};

export default nextConfig;
