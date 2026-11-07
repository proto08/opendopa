# pipeline(Python)。Container Apps Job で `opendopa all` を実行する(Issue #144)。
# ビルドコンテキストはリポジトリのルート:
#   docker build -f pipeline/Dockerfile -t opendopa-pipeline .
# バージョンは mise.toml と合わせる(python 3.13 / uv 0.13.6)。
# 埋め込みは Azure OpenAI(EMBED_PROVIDER=azure)。ローカルモデル用の extra(local)は入れない。
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
WORKDIR /app
COPY pipeline/pyproject.toml pipeline/uv.lock pipeline/
# 先に依存だけを入れる(ソースを変えても層を再利用する)
RUN uv sync --project pipeline --frozen --no-install-project --no-dev
COPY pipeline pipeline
COPY datasets datasets
COPY packages/shared packages/shared
COPY docs/data.md docs/data.md
RUN uv sync --project pipeline --frozen --no-dev

FROM python:3.13-slim AS runtime
RUN useradd --system --create-home --uid 10001 pipeline
WORKDIR /app
COPY --from=build --chown=pipeline /app /app
USER pipeline
ENV PATH=/app/pipeline/.venv/bin:$PATH \
    RAW_SOURCE=blob
# 元 CSV は Blob から取り込み(RAW_SOURCE=blob)、generate → tts → embed → publish を順に実行する
CMD ["opendopa", "all"]
