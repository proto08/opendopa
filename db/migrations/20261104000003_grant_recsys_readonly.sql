-- migrate:up
-- recsys(Rust)用の読み取り専用ロール opendopa_recsys に、起動時に読むテーブルの SELECT だけを与える
-- (設計書 §6.6)。ロール自体は DB の外で作る(ローカルは db/init/01-roles.sql)。
-- ロールがない環境(テストなど)では何もしない。
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'opendopa_recsys') THEN
    GRANT SELECT ON embeddings, clusters, meta TO opendopa_recsys;
    GRANT SELECT (id, dataset_id) ON videos TO opendopa_recsys;
  END IF;
END
$$;

-- migrate:down
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'opendopa_recsys') THEN
    REVOKE SELECT ON embeddings, clusters, meta FROM opendopa_recsys;
    REVOKE SELECT (id, dataset_id) ON videos FROM opendopa_recsys;
  END IF;
END
$$;
