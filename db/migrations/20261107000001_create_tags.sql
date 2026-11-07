-- migrate:up
-- ハッシュタグ(docs/hashtag_design.md §4.2、Issue #150)。
-- opendopa_recsys には権限を足さない(recsys は DB を読まず、候補をリクエストで受け取る)。
CREATE TABLE tags (
  id     text PRIMARY KEY,          -- 'region:hokkaido' / 'dataset:rental'
  kind   text NOT NULL,             -- 'dataset' | 'region'
  label  text NOT NULL,             -- '北海道'(# は付けない)
  yomi   text NOT NULL,             -- 'ほっかいどう'
  sort   int  NOT NULL DEFAULT 0
);

CREATE TABLE video_tags (
  video_id text NOT NULL REFERENCES videos(id),
  tag_id   text NOT NULL REFERENCES tags(id),
  PRIMARY KEY (tag_id, video_id)
);
CREATE INDEX ON video_tags (video_id);

-- migrate:down
DROP TABLE video_tags;
DROP TABLE tags;
