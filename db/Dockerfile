# マイグレーション用イメージ(Container Apps Job で `dbmate up` を流す)。ビルドコンテキストはリポジトリのルート:
#   docker build -f db/Dockerfile -t opendopa-migrate .
# 接続先は環境変数 DATABASE_URL で渡す。dbmate のバージョンは mise.toml と合わせる(2.37.0)。
FROM ghcr.io/amacneil/dbmate:2.37.0
COPY db/migrations /db/migrations
# pg_dump が無いので、スキーマの dump はしない(mise.toml と同じ)
ENV DBMATE_MIGRATIONS_DIR=/db/migrations DBMATE_NO_DUMP_SCHEMA=true
# ENTRYPOINT は dbmate。未適用のマイグレーションだけを流す
CMD ["up"]
