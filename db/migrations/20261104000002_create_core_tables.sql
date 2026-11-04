-- migrate:up
-- 設計書 §5 のテーブル。埋め込みの次元(EMBED_DIM)は 1024。変えるときは新しいマイグレーションを足す。

CREATE TABLE datasets (
  id            text PRIMARY KEY,            -- 例: 'accident'
  label         text NOT NULL,               -- 例: '事故等報告'
  source_name   text NOT NULL,               -- 出典に出す名前
  wm_char       text NOT NULL,               -- 背景の透かし1文字
  color         text NOT NULL                -- 地図の点の色(#RRGGBB)
);

CREATE TABLE videos (
  id            text PRIMARY KEY,            -- 例: 'accident-0001'
  dataset_id    text NOT NULL REFERENCES datasets(id),
  kind          text NOT NULL,               -- 'event' | 'stat' | 'geo'
  category_name text NOT NULL,               -- テロップに出すカテゴリ名
  headline      text NOT NULL,
  duration_sec  real NOT NULL,               -- 15〜30
  scene         jsonb NOT NULL,              -- §9 のシーンJSON(音声URLを含む)
  csv_row       jsonb NOT NULL,              -- [[列名, 値], ...] 元データの表示用
  source_ref    text NOT NULL,               -- 例: '行 #12' または 'YEAR=2023 / 事業者名'
  search_text   text NOT NULL,               -- 埋め込みに使った文
  decisions     jsonb,                       -- 判断モデルの記録(§8.3a)。クライアントには配信しない
  status        text NOT NULL DEFAULT 'ok',  -- 'ok' | 'excluded'
  excluded_why  text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clusters (
  id        int PRIMARY KEY,
  name      text NOT NULL,
  color     text NOT NULL,
  centroid  vector(1024) NOT NULL,
  cx real NOT NULL, cy real NOT NULL          -- 地図上の重心(0〜1)
);

CREATE TABLE embeddings (
  video_id   text PRIMARY KEY REFERENCES videos(id),
  embedding  vector(1024) NOT NULL,           -- 長さ1に正規化済み
  x real NOT NULL, y real NOT NULL,           -- 地図の座標(0〜1)
  cluster_id int REFERENCES clusters(id),
  model      text NOT NULL
);
-- 任意(分析用)。recsys(Rust)は使わない(起動時に全件をメモリへ読む)
CREATE INDEX embeddings_hnsw ON embeddings USING hnsw (embedding vector_cosine_ops);

CREATE TABLE meta (key text PRIMARY KEY, value jsonb NOT NULL);
-- key='centroid': 全動画の重心ベクトル(好みの初期値)

-- 好みのベクトル u は保存しない。view_events と like_events から、recsys が毎回再生して作る(§7.3)。

CREATE TABLE impressions (               -- 配信した動画(見た動画の除外と、出た理由の記録)
  id         bigserial PRIMARY KEY,
  anon_id    text NOT NULL,
  video_id   text NOT NULL REFERENCES videos(id),
  reason     text NOT NULL,              -- 'first' | 'explore_cold' | 'near' | 'adventure'
  served_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (anon_id, video_id)
);

CREATE TABLE view_events (
  id          bigserial PRIMARY KEY,
  view_id     text NOT NULL UNIQUE,      -- クライアントが作るUUID(重複防止)
  anon_id     text NOT NULL,
  video_id    text NOT NULL REFERENCES videos(id),
  watched_sec real NOT NULL,
  ratio       real NOT NULL,             -- サーバーが計算(0〜1)
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE like_events (
  id          bigserial PRIMARY KEY,
  anon_id     text NOT NULL,
  video_id    text NOT NULL REFERENCES videos(id),
  liked       boolean NOT NULL,          -- true=いいね、false=取り消し
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON view_events (anon_id, created_at);
CREATE INDEX ON like_events (anon_id, created_at);

-- migrate:down
DROP TABLE like_events;
DROP TABLE view_events;
DROP TABLE impressions;
DROP TABLE meta;
DROP TABLE embeddings;
DROP TABLE clusters;
DROP TABLE videos;
DROP TABLE datasets;
