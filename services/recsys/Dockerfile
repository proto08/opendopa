# recsys(Rust)。ビルドコンテキストはリポジトリのルート:
#   docker build -f services/recsys/Dockerfile -t opendopa-recsys .
# バージョンは mise.toml と合わせる(rust 1.99.1)。
FROM rust:1.99.1-slim AS build
WORKDIR /src
COPY services/recsys/Cargo.toml services/recsys/Cargo.lock ./
COPY services/recsys/recsys-core recsys-core
COPY services/recsys/recsys-server recsys-server
RUN cargo build --release --locked -p recsys-server

FROM debian:trixie-slim AS runtime
RUN useradd --system --uid 10001 recsys
COPY --from=build /src/target/release/recsys-server /usr/local/bin/recsys-server
USER recsys
ENV PORT=8080
EXPOSE 8080
CMD ["recsys-server"]
