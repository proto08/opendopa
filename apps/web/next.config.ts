import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // コンテナ用の最小構成で出力する(apps/web/Dockerfile)。workspace のパッケージを含めるため、追跡の起点をリポジトリのルートにする
  output: "standalone",
  outputFileTracingRoot: path.join(import.meta.dirname, "../.."),
  cacheComponents: true,
  partialPrefetching: true,
  // workspace の共有パッケージ(TS のまま公開している)をビルドに含める
  transpilePackages: ["@opendopa/shared"],
};

export default nextConfig;
