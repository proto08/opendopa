# web(Next.js, standalone 出力)。ビルドコンテキストはリポジトリのルート:
#   docker build -f apps/web/Dockerfile -t opendopa-web .
# バージョンは mise.toml と合わせる(node 26.13.0 / pnpm 12.16.1)。
FROM node:26.13.0-slim AS build
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH
RUN npm install -g pnpm@12.16.1
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/shared/package.json packages/shared/
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web
COPY packages/shared packages/shared
WORKDIR /repo/apps/web
# public/ が無いリポジトリでも COPY が通るようにする
RUN mkdir -p public && pnpm build

FROM node:26.13.0-slim AS runtime
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
# standalone は outputFileTracingRoot(リポジトリのルート)からの相対パスで出力される
COPY --from=build --chown=node:node /repo/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /repo/apps/web/public ./apps/web/public
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
